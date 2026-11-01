"""Solicitudes de habeas data (Ley 1581, arts. 14 y 15): plazos en días hábiles y respuesta.

Consulta: 10 días hábiles (prorrogables 5). Reclamo: 15 días hábiles (prorrogables 8). Los días hábiles excluyen
sábados, domingos y festivos de Colombia. El texto de la solicitud y de la respuesta puede traer datos personales:
no va a la auditoría (solo el tipo y el estado).
"""
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import fechas
from app.core.festivos import festivo
from app.models.acceso import Usuario
from app.models.habeas import SolicitudDatos
from app.services import auditoria
from app.services.errores import ErrorNegocio, NoEncontrado

PLAZOS = {"consulta": 10, "reclamo": 15}
PRORROGAS = {"consulta": 5, "reclamo": 8}


def es_habil(d: date) -> bool:
    return d.weekday() < 5 and festivo(d) is None


def sumar_habiles(desde: date, dias: int) -> date:
    d = desde
    while dias > 0:
        d += timedelta(days=1)
        if es_habil(d):
            dias -= 1
    return d


def habiles_entre(hoy: date, hasta: date) -> int:
    """Días hábiles que faltan hasta `hasta` (negativo si ya pasó)."""
    if hasta >= hoy:
        return sum(1 for n in range(1, (hasta - hoy).days + 1) if es_habil(hoy + timedelta(days=n)))
    return -sum(1 for n in range((hoy - hasta).days) if es_habil(hasta + timedelta(days=n + 1)))


def a_salida(s: SolicitudDatos) -> dict[str, Any]:
    return {
        **{c: getattr(s, c) for c in (
            "id", "tipo", "titular", "contacto", "descripcion", "recibida_el", "vence_el", "prorrogada",
            "motivo_prorroga", "estado", "respuesta", "respondida_en",
        )},
        "dias_habiles_restantes": habiles_entre(fechas.hoy(), s.vence_el) if s.estado == "en_tramite" else 0,
    }


def listar(db: Session, estado: str | None) -> list[SolicitudDatos]:
    q = select(SolicitudDatos)
    if estado:
        q = q.where(SolicitudDatos.estado == estado)
    return list(db.scalars(q.order_by(SolicitudDatos.estado, SolicitudDatos.vence_el)))


def obtener(db: Session, solicitud_id: uuid.UUID) -> SolicitudDatos:
    s = db.get(SolicitudDatos, solicitud_id)
    if s is None:
        raise NoEncontrado("Solicitud no encontrada.")
    return s


def registrar(db: Session, datos: dict[str, Any], *, actor: Usuario, ip: str | None) -> SolicitudDatos:
    recibida = datos.pop("recibida_el") or fechas.hoy()
    if recibida > fechas.hoy():
        raise ErrorNegocio("La fecha de recibida no puede ser futura.")
    s = SolicitudDatos(**datos, recibida_el=recibida, vence_el=sumar_habiles(recibida, PLAZOS[datos["tipo"]]),
                       registrada_por=actor.id)
    db.add(s)
    db.flush()
    auditoria.registrar(db, accion="habeas.registrar", entidad="solicitud_datos", entidad_id=str(s.id),
                        usuario_id=actor.id, despues={"tipo": s.tipo, "vence_el": s.vence_el.isoformat()}, ip=ip)
    return s


def prorrogar(db: Session, s: SolicitudDatos, motivo: str, *, actor: Usuario, ip: str | None) -> SolicitudDatos:
    """La ley permite ampliar una vez, avisando al titular el motivo antes de que venza."""
    if s.estado != "en_tramite":
        raise ErrorNegocio("La solicitud ya fue respondida.")
    if s.prorrogada:
        raise ErrorNegocio("El plazo solo se puede ampliar una vez.")
    if fechas.hoy() > s.vence_el:
        raise ErrorNegocio("El plazo ya venció: la ampliación se avisa antes del vencimiento.")
    antes = s.vence_el
    s.vence_el, s.prorrogada, s.motivo_prorroga = sumar_habiles(s.vence_el, PRORROGAS[s.tipo]), True, motivo
    auditoria.registrar(db, accion="habeas.prorrogar", entidad="solicitud_datos", entidad_id=str(s.id),
                        usuario_id=actor.id, antes={"vence_el": antes.isoformat()},
                        despues={"vence_el": s.vence_el.isoformat()}, ip=ip)
    return s


def responder(db: Session, s: SolicitudDatos, respuesta: str, *, actor: Usuario, ip: str | None) -> SolicitudDatos:
    if s.estado != "en_tramite":
        raise ErrorNegocio("La solicitud ya fue respondida.")
    s.estado, s.respuesta, s.respondida_en = "respondida", respuesta, fechas.ahora()
    auditoria.registrar(db, accion="habeas.responder", entidad="solicitud_datos", entidad_id=str(s.id),
                        usuario_id=actor.id, despues={"estado": "respondida", "a_tiempo": fechas.hoy() <= s.vence_el},
                        ip=ip)
    return s


def por_vencer(db: Session, dias: int = 3) -> list[SolicitudDatos]:
    """En trámite a `dias` hábiles o menos de vencer (o ya vencidas): para la alerta del Resumen."""
    hoy = fechas.hoy()
    return [s for s in listar(db, "en_tramite") if habiles_entre(hoy, s.vence_el) <= dias]
