import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import validar_politica_password
from app.schemas.comunes import Rama, normalizar_email as _normalizar_email


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalizar_email(v)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre: str
    rol: str
    activo: bool
    rama: Rama | None = None
    permisos: list[str]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario: UsuarioOut


class UsuarioCrear(BaseModel):
    email: str
    nombre: str = Field(min_length=2, max_length=120)
    password: str
    rol: str = Field(min_length=1, max_length=30)
    rama: Rama | None = None  # solo tiene efecto para el Entrenador

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalizar_email(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        validar_politica_password(v)
        return v


class UsuarioActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    rol: str | None = Field(default=None, min_length=1, max_length=30)
    activo: bool | None = None
    rama: Rama | None = None
