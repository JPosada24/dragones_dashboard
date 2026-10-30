"""Resumen del club para el staff: indicadores, alertas que requieren decisión, hoy, rifas y cartera.

Todo se calcula con el mismo filtro de visibilidad del resto de la API: el Entrenador solo ve su rama.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import fechas
from app.core.fechas import formato_fecha, formato_pesos
from app.models.acceso import Usuario
from app.models.alumnos import Alumno, Inscripcion
from app.models.asistencia import Asistencia, Justificacion, Multa, Sesion
from app.models.dominio import ESTADOS_VIGENTES
from app.models.rifas import Rifa, Talonario
from app.models.torneos import OCUPAN_CUPO, EquipoTorneo, Torneo
from app.services import alumnos, asistencia, configuracion, mora

DIAS_VENCE_PRONTO = 7


@dataclass
class Alerta:
    tipo: str  # expulsion | justificaciones | vence_inscripcion | inasistencias | riesgo_mora
    gravedad: int  # 1 = la más urgente
    titulo: str
    detalle: str
    cuando: str
    ruta: str  # pantalla del frontend donde se resuelve


@dataclass
class SesionHoy:
    id: str
    lugar: str | None
    horario: str
    cerrada: bool
    esperados: int
    presentes: int
    justificados: int
    ausentes: int

    @property
    def sin_marcar(self) -> int:
        return self.esperados - self.presentes - self.justificados - self.ausentes


@dataclass
class RifaAnio:
    id: str
    nombre: str
    estado: str
    fecha_sorteo: date
    talonarios: int
    pagados: int


@dataclass
class Resumen:
    alumnos_activos: int = 0
    inscripciones_pendientes: int = 0
    inscripciones_vencen_pronto: int = 0
    multas_pendientes: int = 0
    multas_saldo: int = 0
    alertas: list[Alerta] = field(default_factory=list)
    hoy: list[SesionHoy] = field(default_factory=list)
    rifas: list[RifaAnio] = field(default_factory=list)
    cartera: list[tuple[str, str, int]] = field(default_factory=list)  # (concepto, nota, monto)
    proximo_torneo: dict | None = None


def _nombre(a: Alumno) -> str:
    return f"{a.nombres} {a.apellidos}"


def calcular(db: Session, usuario: Usuario) -> Resumen:
    hoy = fechas.hoy()
    visibles = alumnos.filtro_visibles(usuario)
    permisos = set(usuario.permisos_codigos)
    r = Resumen()

    # ---------- Indicadores ----------
    r.alumnos_activos = db.scalar(
        select(func.count(func.distinct(Alumno.id))).join(Inscripcion, Inscripcion.alumno_id == Alumno.id).where(
            visibles, Alumno.activo.is_(True), Inscripcion.anio == hoy.year, Inscripcion.estado.in_(ESTADOS_VIGENTES)
        )
    )
    pendientes = db.scalars(
        select(Inscripcion).join(Inscripcion.alumno).where(visibles, Inscripcion.estado == "pendiente_pago")
        .order_by(Inscripcion.fecha_limite_pago)
    ).unique().all()
    r.inscripciones_pendientes = len(pendientes)
    pronto = [i for i in pendientes if (i.fecha_limite_pago - hoy).days <= DIAS_VENCE_PRONTO]
    r.inscripciones_vencen_pronto = len(pronto)

    multas = db.scalars(
        select(Multa).join(Multa.alumno).where(visibles, Multa.estado == "pendiente")
    ).unique().all()
    r.multas_pendientes, r.multas_saldo = len(multas), sum(m.valor for m in multas)

    # ---------- Alertas que requieren decisión ----------
    for i in db.scalars(
        select(Inscripcion).join(Inscripcion.alumno).where(visibles, Inscripcion.estado == "a_expulsar")
    ).unique():
        r.alertas.append(Alerta(
            "expulsion", 1, f"{_nombre(i.alumno)} · marcado para expulsión",
            i.motivo or "Pendiente de tu confirmación", "", "/inscripciones",
        ))
    if "justificaciones.revisar" in permisos:
        n = db.scalar(
            select(func.count()).select_from(Justificacion).join(Justificacion.alumno)
            .where(visibles, Justificacion.estado == "pendiente")
        )
        if n:
            r.alertas.append(Alerta(
                "justificaciones", 2, f"{n} justificaci{'ón espera' if n == 1 else 'ones esperan'} aprobación",
                "Hasta que las revises no se decide si hay multa", "", "/asistencia",
            ))
    for i in pronto:
        faltan = (i.fecha_limite_pago - hoy).days
        r.alertas.append(Alerta(
            "vence_inscripcion", 2 if faltan <= 2 else 3, f"{_nombre(i.alumno)} · inscripción por vencer",
            f"Saldo {formato_pesos(i.saldo)}", "hoy" if faltan == 0 else f"en {faltan} d", "/inscripciones",
        ))
    for a in asistencia.alertas(db, usuario):
        r.alertas.append(Alerta(
            "inasistencias", 3, f"{_nombre(a.alumno)} · {a.inasistencias_seguidas} inasistencias seguidas",
            f"Desde el {formato_fecha(a.desde)}, sin justificar", "", "/asistencia",
        ))
    dias_aviso = configuracion.obtener(db, "dias_aviso_mora")
    for s in mora.listar_en_riesgo(db, usuario):
        if not s.en_mora and (s.entra_en_mora - hoy).days <= dias_aviso:
            r.alertas.append(Alerta(
                "riesgo_mora", 3, f"{_nombre(s.alumno)} · deuda próxima a mora",
                f"{formato_pesos(s.total_vencido)} sin pagar", f"el {formato_fecha(s.entra_en_mora)}", "/multas",
            ))
    r.alertas.sort(key=lambda a: a.gravedad)

    # ---------- Entrenamiento de hoy ----------
    for sesion in db.scalars(
        select(Sesion).where(asistencia.filtro_sesiones_visibles(usuario), Sesion.fecha == hoy,
                             Sesion.cancelada.is_(False)).order_by(Sesion.hora_inicio)
    ):
        esperados = {a.id for a in asistencia.esperados_visibles(db, usuario, sesion)}  # Entrenador: su rama
        estados = [
            e for alumno_id, e in db.execute(
                select(Asistencia.alumno_id, Asistencia.estado).where(Asistencia.sesion_id == sesion.id)
            ) if alumno_id in esperados
        ]
        r.hoy.append(SesionHoy(
            str(sesion.id), sesion.lugar,
            f"{sesion.hora_inicio.strftime('%H:%M')}–{sesion.hora_fin.strftime('%H:%M')}",
            sesion.cerrada_en is not None, len(esperados), estados.count("presente"),
            estados.count("justificado"), estados.count("ausente"),
        ))

    # ---------- Rifas del año ----------
    deuda_rifas = 0
    for rifa in db.scalars(select(Rifa).where(Rifa.anio == hoy.year, Rifa.estado != "cancelada").order_by(Rifa.numero)):
        talonarios = db.scalars(
            select(Talonario).join(Talonario.alumno).where(Talonario.rifa_id == rifa.id, visibles)
        ).unique().all()
        r.rifas.append(RifaAnio(str(rifa.id), rifa.nombre, rifa.estado, rifa.fecha_sorteo, len(talonarios),
                                sum(t.pagado for t in talonarios)))
        deuda_rifas += sum(t.saldo for t in talonarios)

    # ---------- Cartera ----------
    r.cartera = [
        ("Inscripciones por cobrar", f"{r.inscripciones_pendientes} pendientes de pago",
         sum(i.saldo for i in pendientes)),
        ("Multas sin pagar", f"{r.multas_pendientes} multas", r.multas_saldo),
        ("Rifas por cobrar", "Talonarios con saldo", deuda_rifas),
    ]

    # ---------- Próximo torneo (solo quien gestiona torneos) ----------
    if "eventos.gestionar" in permisos:
        torneo = db.scalar(
            select(Torneo).where(Torneo.estado == "programado", Torneo.fecha_fin >= hoy)
            .order_by(Torneo.fecha_inicio).limit(1)
        )
        if torneo is not None:
            equipos = db.scalars(select(EquipoTorneo).where(EquipoTorneo.torneo_id == torneo.id)).all()
            ocupados = sum(e.estado in OCUPAN_CUPO for e in equipos)
            por_cobrar = sum(e.valor - e.monto_pagado for e in equipos if e.estado == "pendiente_pago")
            r.proximo_torneo = {
                "id": str(torneo.id), "nombre": torneo.nombre, "rama": torneo.rama,
                "fecha_inicio": torneo.fecha_inicio, "fecha_fin": torneo.fecha_fin, "lugar": torneo.lugar,
                "ocupados": ocupados, "cupo": torneo.cupo_equipos,
            }
            r.cartera.append(("Torneos por cobrar", torneo.nombre, por_cobrar))
    return r
