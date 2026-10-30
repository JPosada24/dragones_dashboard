"""Mora: cualquier deuda sin pagar (multas, talonarios) con más de "meses_mora_expulsion" meses.

Un alumno en mora pasa a "a expulsar" (o a "expulsado" si "expulsion_automatica" está activa). Si se pone al
día, el sistema lo devuelve a "activo", pero solo si fue el sistema quien lo marcó (causa "mora"), nunca si
fue una decisión manual. La revisión es idempotente: la corre el worker.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import fechas
from app.core.fechas import formato_fecha, formato_pesos
from app.models.acceso import Usuario
from app.models.alumnos import Alumno, Inscripcion
from app.models.asistencia import Multa
from app.models.rifas import RIFA_FUERA, Rifa, Talonario
from app.services import alumnos, auditoria, configuracion, notificaciones


@dataclass
class Deuda:
    concepto: str
    monto: int
    vence: date  # desde cuándo se debe


@dataclass
class Situacion:
    alumno: Alumno
    deudas: list[Deuda] = field(default_factory=list)
    vencida_desde: date | None = None  # la deuda vencida más antigua
    entra_en_mora: date | None = None  # vencida_desde + meses de mora
    en_mora: bool = False

    @property
    def total_vencido(self) -> int:
        return sum(d.monto for d in self.deudas if d.vence <= fechas.hoy())


def deudas_de(db: Session, alumno: Alumno) -> list[Deuda]:
    """La multa se debe desde la sesión; el talonario, desde el sorteo (antes aún no se debe)."""
    deudas = [
        Deuda(f"Multa del {formato_fecha(m.sesion.fecha)}", m.valor, m.sesion.fecha)
        for m in db.scalars(select(Multa).where(Multa.alumno_id == alumno.id, Multa.estado == "pendiente")).unique()
    ]
    talonarios = db.scalars(
        select(Talonario).join(Talonario.rifa).where(Talonario.alumno_id == alumno.id, Rifa.estado.not_in(RIFA_FUERA))
    ).unique()
    deudas += [
        Deuda(f"Talonario de «{t.rifa.nombre}»", t.saldo, t.rifa.fecha_sorteo) for t in talonarios if t.saldo > 0
    ]
    return sorted(deudas, key=lambda d: d.vence)


def situacion(db: Session, alumno: Alumno, *, hoy: date | None = None) -> Situacion:
    hoy = hoy or fechas.hoy()
    s = Situacion(alumno, deudas_de(db, alumno))
    vencidas = [d for d in s.deudas if d.vence <= hoy]
    if vencidas:
        s.vencida_desde = vencidas[0].vence
        s.entra_en_mora = fechas.sumar_meses(s.vencida_desde, configuracion.obtener(db, "meses_mora_expulsion"))
        s.en_mora = hoy >= s.entra_en_mora
    return s


def _inscripcion_vigente(db: Session, alumno_id) -> Inscripcion | None:
    """La más reciente activa o a expulsar (en enero sigue valiendo la del año anterior hasta que se renueve)."""
    return db.scalar(
        select(Inscripcion)
        .where(Inscripcion.alumno_id == alumno_id, Inscripcion.estado.in_(("activo", "a_expulsar")))
        .order_by(Inscripcion.anio.desc()).limit(1)
    )


def listar_en_riesgo(db: Session, usuario: Usuario) -> list[Situacion]:
    """Alumnos visibles con deuda vencida, de la más antigua a la más reciente."""
    resultado = []
    q = select(Alumno).where(Alumno.activo.is_(True), alumnos.filtro_visibles(usuario))
    for alumno in db.scalars(q):
        s = situacion(db, alumno)
        if s.vencida_desde is not None:
            resultado.append(s)
    return sorted(resultado, key=lambda s: s.vencida_desde)


def _detalle(s: Situacion) -> str:
    return "; ".join(f"{d.concepto}: {formato_pesos(d.monto)}" for d in s.deudas if d.vence <= fechas.hoy())


@dataclass
class ResultadoMora:
    a_expulsar: int = 0
    expulsados: int = 0
    al_dia: int = 0
    avisos: int = 0


def revisar(db: Session) -> ResultadoMora:
    """Aplica la regla de mora a todos los alumnos con inscripción activa o a expulsar."""
    hoy = fechas.hoy()
    automatica = configuracion.obtener(db, "expulsion_automatica")
    dias_aviso = configuracion.obtener(db, "dias_aviso_mora")
    r = ResultadoMora()
    inscripciones = db.scalars(
        select(Inscripcion).where(Inscripcion.estado.in_(("activo", "a_expulsar"))).with_for_update(of=Inscripcion)
    ).unique().all()
    vistos = set()
    for i in sorted(inscripciones, key=lambda x: -x.anio):
        if i.alumno_id in vistos:  # solo la inscripción más reciente de cada alumno
            continue
        vistos.add(i.alumno_id)
        alumno = i.alumno
        s = situacion(db, alumno, hoy=hoy)
        familia = notificaciones.destinatarios_de_alumno(db, alumno)

        if i.estado == "activo" and s.en_mora:
            antes = i.estado
            i.estado = "expulsado" if automatica else "a_expulsar"
            i.causa_expulsion = "mora"
            i.motivo = f"Mora: deuda sin pagar desde el {formato_fecha(s.vencida_desde)}"[:255]
            auditoria.registrar(
                db, accion="inscripcion.mora", entidad="inscripcion", entidad_id=str(i.id),
                antes={"estado": antes}, despues={"estado": i.estado, "total_vencido": s.total_vencido},
            )
            notificaciones.avisar(
                db, familia, tipo="mora", clave=f"mora:{i.id}:{s.vencida_desde.isoformat()}", alumno_id=alumno.id,
                titulo="Deuda en mora",
                mensaje=(f"{alumno.nombres} tiene deudas sin pagar desde el {formato_fecha(s.vencida_desde)} "
                         f"({_detalle(s)}). Su inscripción quedó "
                         f"{'cancelada por mora' if automatica else 'en revisión para expulsión'}. "
                         "Comunícate con el club para ponerte al día."),
            )
            if not automatica:
                notificaciones.avisar(
                    db, notificaciones.staff_de_rama(db, alumno.rama), tipo="mora_staff", alumno_id=alumno.id,
                    clave=f"mora_staff:{i.id}:{s.vencida_desde.isoformat()}", titulo="Expulsión por confirmar",
                    mensaje=(f"{alumno.nombres} {alumno.apellidos} quedó «a expulsar» por mora "
                             f"({formato_pesos(s.total_vencido)} sin pagar desde el {formato_fecha(s.vencida_desde)}). "
                             "Confirma la expulsión o espera a que se ponga al día."),
                )
            if automatica:
                r.expulsados += 1
            else:
                r.a_expulsar += 1

        elif i.estado == "a_expulsar" and i.causa_expulsion == "mora" and not s.en_mora:
            i.estado, i.causa_expulsion, i.motivo = "activo", None, None
            auditoria.registrar(
                db, accion="inscripcion.fin_mora", entidad="inscripcion", entidad_id=str(i.id),
                antes={"estado": "a_expulsar"}, despues={"estado": "activo"},
            )
            notificaciones.avisar(
                db, familia, tipo="fin_mora", clave=f"fin_mora:{i.id}:{hoy.isoformat()}", alumno_id=alumno.id,
                titulo="Ya estás al día",
                mensaje=f"{alumno.nombres} ya no tiene deudas en mora: su inscripción sigue activa.",
            )
            r.al_dia += 1

        elif i.estado == "activo" and s.entra_en_mora and 0 < (s.entra_en_mora - hoy).days <= dias_aviso:
            r.avisos += notificaciones.avisar(
                db, familia, tipo="aviso_mora", alumno_id=alumno.id,
                clave=f"aviso_mora:{i.id}:{s.entra_en_mora.isoformat()}", titulo="Aviso: deuda próxima a mora",
                mensaje=(f"{alumno.nombres} tiene deudas sin pagar ({_detalle(s)}). Si no se pagan antes del "
                         f"{formato_fecha(s.entra_en_mora)}, su inscripción pasará a revisión para expulsión."),
            )
    db.flush()
    return r
