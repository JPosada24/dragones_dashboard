"""Programación automática de entrenamientos a partir del horario semanal.

- Crea las sesiones de los próximos `dias_programacion_anticipada` días (desde mañana: la de hoy nunca se
  crea ni se mueve sola, para no multar a nadie por una sesión que no existía).
- Festivo de Colombia → la sesión se crea cancelada. Torneo del club ese día → se cancela; si el torneo se
  cancela, la sesión vuelve. Las sesiones extra (creadas a mano) no se tocan.
- Idempotente: la puede correr el worker cada hora y también tras cada cambio de horario o de torneos.
"""
import uuid
from dataclasses import dataclass
from datetime import date, time, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core import fechas, festivos
from app.models.acceso import Usuario
from app.models.asistencia import Asistencia, HorarioEntrenamiento, Justificacion, Sesion
from app.models.torneos import Torneo
from app.services import auditoria, configuracion
from app.services.errores import ErrorNegocio


@dataclass
class DiaHorario:
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    lugar: str | None


@dataclass
class ResultadoProgramacion:
    creadas: int = 0
    canceladas: int = 0
    reactivadas: int = 0
    eliminadas: int = 0

    @property
    def hubo_cambios(self) -> bool:
        return any((self.creadas, self.canceladas, self.reactivadas, self.eliminadas))


def horario(db: Session) -> list[HorarioEntrenamiento]:
    return list(db.scalars(select(HorarioEntrenamiento).order_by(HorarioEntrenamiento.dia_semana)))


def _torneos_por_fecha(db: Session, desde: date, hasta: date) -> dict[date, str]:
    resultado: dict[date, str] = {}
    for t in db.scalars(select(Torneo).where(
        Torneo.estado == "programado", Torneo.fecha_inicio <= hasta, Torneo.fecha_fin >= desde,
    ).order_by(Torneo.fecha_inicio)):
        d = max(t.fecha_inicio, desde)
        while d <= min(t.fecha_fin, hasta):
            resultado.setdefault(d, t.nombre)
            d += timedelta(days=1)
    return resultado


def _tiene_registros(db: Session, sesion_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(select(exists().where(Asistencia.sesion_id == sesion_id)))
        or db.scalar(select(exists().where(Justificacion.sesion_id == sesion_id)))
    )


def generar(db: Session) -> ResultadoProgramacion:
    r = ResultadoProgramacion()
    desde = fechas.hoy() + timedelta(days=1)
    hasta = fechas.hoy() + timedelta(days=configuracion.obtener(db, "dias_programacion_anticipada"))
    if hasta < desde:
        return r
    por_dia = {h.dia_semana: h for h in horario(db)}
    torneos = _torneos_por_fecha(db, desde, hasta)
    existentes = {
        (s.fecha, s.hora_inicio): s
        for s in db.scalars(select(Sesion).where(Sesion.fecha.between(desde, hasta)).with_for_update())
    }

    # 1) Sesiones automáticas ya creadas: torneos nuevos o cancelados.
    for s in existentes.values():
        if not s.automatica or s.cerrada_en is not None:
            continue
        h = por_dia.get(s.fecha.weekday())
        torneo = torneos.get(s.fecha)
        if not s.cancelada and torneo:
            s.cancelada, s.causa_cancelacion, s.motivo_cancelacion = True, "torneo", f"Torneo: {torneo}"
            r.canceladas += 1
        elif (
            s.cancelada and s.causa_cancelacion in ("torneo", "horario") and not torneo
            and not festivos.festivo(s.fecha) and h is not None and h.hora_inicio == s.hora_inicio
        ):
            s.cancelada, s.causa_cancelacion, s.motivo_cancelacion = False, None, None
            s.hora_fin, s.lugar = h.hora_fin, h.lugar
            r.reactivadas += 1

    # 2) Sesiones que faltan según el horario.
    d = desde
    while d <= hasta:
        h = por_dia.get(d.weekday())
        if h is not None and (d, h.hora_inicio) not in existentes:
            sesion = Sesion(fecha=d, hora_inicio=h.hora_inicio, hora_fin=h.hora_fin, lugar=h.lugar, automatica=True)
            festivo = festivos.festivo(d)
            if festivo:
                sesion.cancelada, sesion.causa_cancelacion = True, "festivo"
                sesion.motivo_cancelacion = f"Festivo: {festivo}"
            elif d in torneos:
                sesion.cancelada, sesion.causa_cancelacion = True, "torneo"
                sesion.motivo_cancelacion = f"Torneo: {torneos[d]}"
            db.add(sesion)
            r.creadas += 1
        d += timedelta(days=1)
    db.flush()
    return r


def actualizar_horario(
    db: Session, *, dias: list[DiaHorario], actor: Usuario, ip: str | None
) -> ResultadoProgramacion:
    """Reemplaza el horario semanal y ajusta las sesiones automáticas desde mañana."""
    if len({d.dia_semana for d in dias}) != len(dias):
        raise ErrorNegocio("Hay un día repetido en el horario.")
    antes = [_dia_a_dict(h) for h in horario(db)]
    for fila in horario(db):
        db.delete(fila)
    db.flush()
    db.add_all(HorarioEntrenamiento(
        dia_semana=d.dia_semana, hora_inicio=d.hora_inicio, hora_fin=d.hora_fin, lugar=d.lugar,
    ) for d in dias)
    db.flush()

    r = ResultadoProgramacion()
    por_dia = {d.dia_semana: d for d in dias}
    manana = fechas.hoy() + timedelta(days=1)
    for s in db.scalars(select(Sesion).where(
        Sesion.automatica.is_(True), Sesion.fecha >= manana, Sesion.cerrada_en.is_(None),
    ).with_for_update()):
        nuevo = por_dia.get(s.fecha.weekday())
        if nuevo is not None and nuevo.hora_inicio == s.hora_inicio:
            s.hora_fin, s.lugar = nuevo.hora_fin, nuevo.lugar  # mismo día y hora de inicio: solo se ajusta
        elif _tiene_registros(db, s.id):
            # Ya hay justificaciones o marcas: se conserva como evidencia, cancelada.
            if not s.cancelada:
                s.cancelada, s.causa_cancelacion, s.motivo_cancelacion = True, "horario", "Cambio de horario"
                r.canceladas += 1
        else:
            db.delete(s)
            r.eliminadas += 1
    db.flush()

    generada = generar(db)
    r.creadas, r.canceladas, r.reactivadas = generada.creadas, r.canceladas + generada.canceladas, generada.reactivadas
    auditoria.registrar(
        db, accion="horario.actualizar", entidad="horario_entrenamiento", entidad_id="semana", usuario_id=actor.id,
        ip=ip, antes={"dias": antes}, despues={
            "dias": [_dia_a_dict(d) for d in dias], "creadas": r.creadas, "eliminadas": r.eliminadas,
            "canceladas": r.canceladas,
        },
    )
    return r


def _dia_a_dict(d: HorarioEntrenamiento | DiaHorario) -> dict:
    return {
        "dia_semana": d.dia_semana, "hora_inicio": d.hora_inicio.strftime("%H:%M"),
        "hora_fin": d.hora_fin.strftime("%H:%M"), "lugar": d.lugar,
    }
