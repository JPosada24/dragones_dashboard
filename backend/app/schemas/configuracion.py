from typing import Any

from pydantic import BaseModel


class ConfigOut(BaseModel):
    clave: str
    valor: Any
    descripcion: str | None


class ConfigActualizar(BaseModel):
    valor: Any


class PermisoOut(BaseModel):
    codigo: str
    descripcion: str


class RolOut(BaseModel):
    codigo: str
    nombre: str
    descripcion: str | None
    permisos: list[str]


class RolesOut(BaseModel):
    """Matriz de roles y permisos tal como está en la base de datos (solo lectura)."""

    permisos: list[PermisoOut]
    roles: list[RolOut]
