import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, usuario_actual
from app.core.config import get_settings
from app.core.correo import get_correo
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.notificaciones import Notificacion
from app.schemas.notificaciones import (
    ConteoOut,
    CorreoEstadoOut,
    MarcarWhatsAppIn,
    NotificacionOut,
    ResultadoPruebaOut,
    WhatsAppOut,
)
from app.services import auditoria
from app.services import notificaciones as servicio

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])
GESTIONAR = requiere("notificaciones.gestionar")


def _out(n: Notificacion) -> NotificacionOut:
    return NotificacionOut(
        id=n.id, tipo=n.tipo, titulo=n.titulo, mensaje=n.mensaje, alumno_id=n.alumno_id,
        leida=n.leida_en is not None, creado_en=n.creado_en,
    )


def _enmascarar_email(email: str) -> str:
    usuario, _, dominio = email.partition("@")
    return f"{usuario[:2]}***@{dominio}"


# ---------- Bandeja propia (cualquier usuario con sesión) ----------
@router.get("/mias", response_model=list[NotificacionOut])
def mias(
    no_leidas: bool = False,
    limit: int = Query(50, ge=1, le=200),
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> list[NotificacionOut]:
    return [_out(n) for n in servicio.mias(db, usuario, solo_no_leidas=no_leidas, limit=limit)]


@router.post("/mias/leer-todas", response_model=ConteoOut)
def leer_todas(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)) -> ConteoOut:
    n = servicio.marcar_todas_leidas(db, usuario)
    db.commit()
    return ConteoOut(marcadas=n)


@router.post("/{notificacion_id}/leer", response_model=NotificacionOut)
def leer(
    notificacion_id: uuid.UUID, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)
) -> NotificacionOut:
    n = servicio.marcar_leida(db, usuario, notificacion_id)
    db.commit()
    return _out(n)


# ---------- WhatsApp (staff) ----------
@router.get("/whatsapp", response_model=list[WhatsAppOut])
def cola_whatsapp(
    limit: int = Query(100, ge=1, le=500), _: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db)
) -> list[WhatsAppOut]:
    """Avisos listos para enviar desde el WhatsApp del club: cada uno trae su enlace con el mensaje escrito."""
    return [
        WhatsAppOut(
            id=n.id, tipo=n.tipo, titulo=n.titulo, telefono=n.telefono_destino, mensaje=n.mensaje,
            enlace=servicio.enlace_whatsapp(n.telefono_destino, n.mensaje), creado_en=n.creado_en,
        )
        for n in servicio.cola_whatsapp(db, limit=limit)
    ]


@router.post("/{notificacion_id}/whatsapp", status_code=204)
def marcar_whatsapp(
    notificacion_id: uuid.UUID, datos: MarcarWhatsAppIn, request: Request,
    actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> None:
    servicio.marcar_whatsapp(db, notificacion_id, accion=datos.accion, actor=actor, ip=ip_cliente(request))
    db.commit()


# ---------- Correo (staff) ----------
@router.get("/correos", response_model=list[CorreoEstadoOut])
def estado_correos(
    estado: str | None = Query(None, pattern="^(pendiente|enviado|fallido)$"),
    limit: int = Query(100, ge=1, le=500),
    _: Usuario = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> list[CorreoEstadoOut]:
    q = select(Notificacion).where(Notificacion.email_destino.is_not(None))
    if estado:
        q = q.where(Notificacion.email_estado == estado)
    filas = db.scalars(q.order_by(Notificacion.creado_en.desc()).limit(limit))
    return [
        CorreoEstadoOut(
            id=n.id, tipo=n.tipo, titulo=n.titulo, email=_enmascarar_email(n.email_destino), estado=n.email_estado,
            intentos=n.email_intentos, error=n.email_error, creado_en=n.creado_en,
        )
        for n in filas
    ]


@router.post("/correo-prueba", response_model=ResultadoPruebaOut)
def correo_prueba(
    request: Request, actor: Usuario = Depends(requiere("config.editar")), db: Session = Depends(get_db)
) -> ResultadoPruebaOut:
    """Envía un correo de prueba a tu propio correo para comprobar la configuración SMTP (p. ej. Gmail)."""
    modo = get_settings().email_modo
    try:
        get_correo().enviar(actor.email, f"[{get_settings().club_nombre}] Correo de prueba",
                            "Si recibes este mensaje, el correo del club quedó bien configurado.")
        resultado = ResultadoPruebaOut(enviado=True, modo=modo, detalle=f"Enviado a {_enmascarar_email(actor.email)}.")
    except Exception as e:
        resultado = ResultadoPruebaOut(enviado=False, modo=modo, detalle=f"{type(e).__name__}: {e}"[:300])
    auditoria.registrar(db, accion="notificacion.correo_prueba", entidad="configuracion", usuario_id=actor.id,
                        despues={"enviado": resultado.enviado, "modo": modo}, ip=ip_cliente(request))
    db.commit()
    return resultado
