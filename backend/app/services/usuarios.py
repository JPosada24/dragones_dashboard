import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.acceso import Rol, SesionRefresh, Usuario


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
