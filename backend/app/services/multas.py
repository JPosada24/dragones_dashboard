"""Multas por inasistencia: generación (desde la asistencia), pago y anulación."""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import fechas
from app.models.acceso import Usuario
from app.models.alumnos import Alumno
from app.models.asistencia import Multa, Sesion
from app.services import alumnos, auditoria, configuracion
from app.services.errores import Conflicto, ErrorNegocio, NoEncontrado


def _auditar(db: Session, accion: str, m: Multa, actor_id: uuid.UUID | None, ip: str | None, **extra) -> None:
    auditoria.registrar(
        db, accion=accion, entidad="multa", entidad_id=str(m.id), usuario_id=actor_id, ip=ip, **extra,
    )


def vigente(db: Session, sesion_id: uuid.UUID, alumno_id: uuid.UUID) -> Multa | None:
    return db.scalar(select(Multa).where(
        Multa.sesion_id == sesion_id, Multa.alumno_id == alumno_id, Multa.estado.in_(("pendiente", "pagada"))
    ))


def generar(
    db: Session, sesion: Sesion, alumno_id: uuid.UUID, *, actor_id: uuid.UUID | None = None, ip: str | None = None
) -> Multa | None:
    """Crea la multa de una inasistencia si no existe. El valor se toma de "configuracion" en ese momento."""
    existente = vigente(db, sesion.id, alumno_id)
    if existente is not None:
        return existente
    valor = configuracion.obtener(db, "multa_inasistencia")
    if valor <= 0:  # el SuperAdmin puede desactivar las multas poniendo el valor en 0
        return None
    multa = Multa(alumno_id=alumno_id, sesion_id=sesion.id, valor=valor, estado="pendiente")
    db.add(multa)
    db.flush()
    _auditar(
        db, "multa.generar", multa, actor_id, ip,
        despues={"alumno_id": str(alumno_id), "sesion_id": str(sesion.id), "valor": valor},
    )
    return multa


def anular_si_pendiente(
    db: Session, sesion_id: uuid.UUID, alumno_id: uuid.UUID, *, motivo: str,
    actor_id: uuid.UUID | None, ip: str | None,
) -> Multa | None:
    """Anula la multa de esa inasistencia si sigue pendiente. Una ya pagada no se toca (devolverla es manual)."""
    multa = vigente(db, sesion_id, alumno_id)
    if multa is None or multa.estado != "pendiente":
        return None
    multa.estado, multa.motivo_anulacion, multa.anulada_por = "anulada", motivo[:255], actor_id
    db.flush()
    _auditar(db, "multa.anular", multa, actor_id, ip, antes={"estado": "pendiente"}, despues={"motivo": motivo})
    return multa


# ---------- Consultas ----------
def listar(
    db: Session, usuario: Usuario, *, estado: str | None, alumno_id: uuid.UUID | None, rama: str | None,
    skip: int, limit: int,
) -> list[Multa]:
    q = select(Multa).join(Multa.alumno).join(Multa.sesion).where(alumnos.filtro_visibles(usuario))
    if estado:
        q = q.where(Multa.estado == estado)
    if alumno_id:
        q = q.where(Multa.alumno_id == alumno_id)
    if rama:
        q = q.where(Alumno.rama == rama)
    q = q.order_by(Sesion.fecha.desc(), Alumno.apellidos).offset(skip).limit(limit)
    return list(db.scalars(q).unique())


def obtener_visible(db: Session, usuario: Usuario, multa_id: uuid.UUID) -> Multa:
    multa = db.scalar(
        select(Multa).join(Multa.alumno).where(Multa.id == multa_id, alumnos.filtro_visibles(usuario))
    )
    if multa is None:
        raise NoEncontrado("Multa no encontrada.")
    return multa


# ---------- Acciones ----------
def pagar(db: Session, m: Multa, *, fecha_pago: date, actor: Usuario, ip: str | None) -> Multa:
    if m.estado != "pendiente":
        raise Conflicto(f"La multa no está pendiente (estado: {m.estado}).")
    if fecha_pago > fechas.hoy():
        raise ErrorNegocio("La fecha de pago no puede ser futura.")
    if fecha_pago < m.sesion.fecha:
        raise ErrorNegocio("La fecha de pago no puede ser anterior a la sesión.")
    m.estado, m.fecha_pago, m.pago_registrado_por = "pagada", fecha_pago, actor.id
    db.flush()
    _auditar(
        db, "multa.pagar", m, actor.id, ip,
        antes={"estado": "pendiente"}, despues={"estado": "pagada", "fecha_pago": fecha_pago.isoformat()},
    )
    return m


def anular(db: Session, m: Multa, *, motivo: str, actor: Usuario, ip: str | None) -> Multa:
    if m.estado != "pendiente":
        raise Conflicto("Solo se puede anular una multa pendiente.")
    anular_si_pendiente(db, m.sesion_id, m.alumno_id, motivo=motivo, actor_id=actor.id, ip=ip)
    return m
