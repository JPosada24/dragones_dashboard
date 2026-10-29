"""Inicio de sesión, emisión y rotación de refresh tokens."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.models.acceso import SesionRefresh, Usuario
from app.services import auditoria


class ErrorAuth(Exception):
    """Falla de autenticación. Mensaje genérico a propósito: no revela qué falló."""


def autenticar(db: Session, email: str, password: str, ip: str | None) -> Usuario:
    s = get_settings()
    ahora = datetime.now(timezone.utc)
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))

    if usuario is None:
        security.verificar_password_falso(password)
        auditoria.registrar(db, accion="auth.login_fallido", entidad="usuario", despues={"email": email}, ip=ip)
        db.commit()
        raise ErrorAuth

    if not usuario.activo or (usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora):
        security.verificar_password_falso(password)
        auditoria.registrar(
            db, accion="auth.login_rechazado", entidad="usuario", entidad_id=str(usuario.id),
            usuario_id=usuario.id, ip=ip,
        )
        db.commit()
        raise ErrorAuth

    if not security.verificar_password(usuario.password_hash, password):
        usuario.intentos_fallidos += 1
        auditoria.registrar(
            db, accion="auth.login_fallido", entidad="usuario", entidad_id=str(usuario.id),
            usuario_id=usuario.id, ip=ip,
        )
        if usuario.intentos_fallidos >= s.max_intentos_login:
            usuario.bloqueado_hasta = ahora + timedelta(minutes=s.bloqueo_minutos)
            usuario.intentos_fallidos = 0
            auditoria.registrar(
                db, accion="auth.cuenta_bloqueada", entidad="usuario", entidad_id=str(usuario.id),
                usuario_id=usuario.id, ip=ip,
            )
        db.commit()
        raise ErrorAuth

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora
    if security.necesita_rehash(usuario.password_hash):
        usuario.password_hash = security.hash_password(password)
    auditoria.registrar(
        db, accion="auth.login", entidad="usuario", entidad_id=str(usuario.id),
        usuario_id=usuario.id, ip=ip,
    )
    return usuario


def emitir_sesion(
    db: Session,
    usuario: Usuario,
    ip: str | None,
    user_agent: str | None,
    familia_id: uuid.UUID | None = None,
) -> tuple[str, int, str]:
    """Devuelve (access_token, segundos_de_vida, refresh_token_plano). No hace commit."""
    s = get_settings()
    access, vida = security.crear_access_token(usuario.id, usuario.rol.codigo)
    refresh = security.nuevo_refresh_token()
    db.add(
        SesionRefresh(
            usuario_id=usuario.id,
            familia_id=familia_id or uuid.uuid4(),
            token_hash=security.hash_refresh_token(refresh),
            expira_en=datetime.now(timezone.utc) + timedelta(days=s.refresh_token_dias),
            user_agent=user_agent,
            ip=ip,
        )
    )
    return access, vida, refresh


def rotar_refresh(
    db: Session, token_plano: str, ip: str | None, user_agent: str | None
) -> tuple[Usuario, str, int, str]:
    """Canjea un refresh token por uno nuevo. Si se reutiliza uno ya usado, se revoca toda la familia."""
    ahora = datetime.now(timezone.utc)
    sesion = db.scalar(
        select(SesionRefresh)
        .where(SesionRefresh.token_hash == security.hash_refresh_token(token_plano))
        .with_for_update()
    )
    if sesion is None:
        raise ErrorAuth

    if sesion.revocado_en is not None:
        # Alguien presentó un token ya rotado: posible robo. Se invalida toda la cadena.
        db.execute(
            update(SesionRefresh)
            .where(SesionRefresh.familia_id == sesion.familia_id, SesionRefresh.revocado_en.is_(None))
            .values(revocado_en=ahora)
        )
        auditoria.registrar(
            db, accion="auth.refresh_reutilizado", entidad="usuario", entidad_id=str(sesion.usuario_id),
            usuario_id=sesion.usuario_id, ip=ip,
        )
        db.commit()
        raise ErrorAuth

    usuario = db.get(Usuario, sesion.usuario_id)
    if sesion.expira_en <= ahora or usuario is None or not usuario.activo:
        sesion.revocado_en = ahora
        db.commit()
        raise ErrorAuth

    sesion.revocado_en = ahora
    access, vida, refresh = emitir_sesion(db, usuario, ip, user_agent, familia_id=sesion.familia_id)
    db.commit()
    return usuario, access, vida, refresh


def cerrar_sesion(db: Session, token_plano: str) -> None:
    """Revoca la familia completa del refresh token. Si el token no existe, no hace nada."""
    sesion = db.scalar(
        select(SesionRefresh).where(SesionRefresh.token_hash == security.hash_refresh_token(token_plano))
    )
    if sesion is None:
        return
    db.execute(
        update(SesionRefresh)
        .where(SesionRefresh.familia_id == sesion.familia_id, SesionRefresh.revocado_en.is_(None))
        .values(revocado_en=datetime.now(timezone.utc))
    )
    db.commit()
