import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.fechas import ahora
from app.core.security import hash_password
from app.models.acceso import Rol, SesionRefresh, Usuario
from app.models.alumnos import Acudiente, Alumno
from app.services import auditoria
from app.services.errores import ErrorNegocio


class EmailDuplicado(Exception):
    pass


class RolNoExiste(Exception):
    pass


def obtener_rol(db: Session, codigo: str) -> Rol:
    rol = db.scalar(select(Rol).where(Rol.codigo == codigo))
    if rol is None:
        raise RolNoExiste(codigo)
    return rol


def crear_usuario(
    db: Session, *, email: str, nombre: str, password: str, rol_codigo: str
) -> Usuario:
    """Crea el usuario. La contraseña ya debe haber pasado la política (el esquema la valida)."""
    if db.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
        raise EmailDuplicado(email)
    rol = obtener_rol(db, rol_codigo)
    usuario = Usuario(email=email, nombre=nombre, password_hash=hash_password(password), rol=rol)
    db.add(usuario)
    db.flush()
    return usuario


def revocar_sesiones(db: Session, usuario_id: uuid.UUID) -> None:
    db.execute(
        update(SesionRefresh)
        .where(SesionRefresh.usuario_id == usuario_id, SesionRefresh.revocado_en.is_(None))
        .values(revocado_en=datetime.now(UTC))
    )


def eliminar_usuario(db: Session, usuario: Usuario, *, actor: Usuario, ip: str | None) -> None:
    """Elimina una cuenta: nadie vuelve a entrar con ella y su correo queda libre para otra cuenta.

    No se borra la fila: pagos, asistencias, actas y la auditoría guardan quién los registró (y la auditoría no se
    toca). Se conserva solo el nombre, para que ese historial siga diciendo quién fue; el correo se descarta.
    """
    if usuario.id == actor.id:
        raise ErrorNegocio("No puedes eliminar tu propia cuenta.")
    vinculo = None
    for modelo in (Alumno, Acudiente):
        fila = db.scalar(select(modelo).where(modelo.usuario_id == usuario.id))
        if fila is not None:
            vinculo = f"{modelo.__tablename__}:{fila.id}"
            fila.usuario_id = None  # el alumno o acudiente sigue; solo pierde la cuenta
    antes = {"rol": usuario.rol.codigo, "activo": usuario.activo, "vinculo": vinculo}
    usuario.email = f"eliminado-{usuario.id.hex}@usuarios.invalid"
    usuario.password_hash = hash_password(secrets.token_urlsafe(32))  # nadie la conoce
    usuario.activo = False
    usuario.credenciales_version += 1  # los tokens que tenga dejan de valer al instante
    usuario.eliminado_en = ahora()
    revocar_sesiones(db, usuario.id)
    db.flush()
    auditoria.registrar(
        db, accion="usuario.eliminar", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        antes=antes, despues={"eliminado": True}, ip=ip,
    )
