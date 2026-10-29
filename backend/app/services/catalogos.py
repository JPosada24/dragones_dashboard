"""Siembra idempotente de permisos, roles, parámetros y primer SuperAdmin."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import PERMISOS, ROLES, ROLES_PERMISOS
from app.core.security import validar_politica_password
from app.models.acceso import Permiso, Rol, Usuario
from app.models.sistema import Configuracion
from app.services import usuarios
from app.services.configuracion import DEFAULTS


def sembrar_catalogos(db: Session) -> None:
    permisos = {p.codigo: p for p in db.scalars(select(Permiso))}
    for codigo, descripcion in PERMISOS.items():
        if codigo in permisos:
            permisos[codigo].descripcion = descripcion
        else:
            permisos[codigo] = Permiso(codigo=codigo, descripcion=descripcion)
            db.add(permisos[codigo])

    roles = {r.codigo: r for r in db.scalars(select(Rol))}
    for codigo, (nombre, descripcion) in ROLES.items():
        if codigo in roles:
            roles[codigo].nombre, roles[codigo].descripcion = nombre, descripcion
        else:
            roles[codigo] = Rol(codigo=codigo, nombre=nombre, descripcion=descripcion)
            db.add(roles[codigo])
    db.flush()

    for codigo, rol in roles.items():
        if codigo in ROLES_PERMISOS:
            rol.permisos = [permisos[c] for c in sorted(ROLES_PERMISOS[codigo])]

    existentes = set(db.scalars(select(Configuracion.clave)))
    for clave, (valor, descripcion) in DEFAULTS.items():
        if clave not in existentes:
            db.add(Configuracion(clave=clave, valor=valor, descripcion=descripcion))
    db.commit()


def sembrar_superadmin(db: Session) -> str:
    """Crea el SuperAdmin inicial si no existe. Devuelve un mensaje para el log."""
    s = get_settings()
    if not s.superadmin_email or not s.superadmin_password:
        return "SUPERADMIN_EMAIL/SUPERADMIN_PASSWORD no definidos: no se crea superadmin."
    email = s.superadmin_email.strip().lower()
    if db.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
        return f"El superadmin {email} ya existe."
    validar_politica_password(s.superadmin_password)
    usuarios.crear_usuario(
        db, email=email, nombre=s.superadmin_nombre, password=s.superadmin_password, rol_codigo="SUPERADMIN"
    )
    db.commit()
    return f"Superadmin {email} creado."
