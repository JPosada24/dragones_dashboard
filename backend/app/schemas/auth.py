import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.security import validar_politica_password
from app.schemas.comunes import normalizar_email as _normalizar_email


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
    permisos: list[str]


class UsuarioListaOut(UsuarioOut):
    vinculado_a: str | None = None  # "Alumno F012 · Laura Pérez" o "Acudiente de F012 · Laura Pérez"


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105  (tipo de token OAuth2, no es una contraseña)
    expires_in: int
    usuario: UsuarioOut


class UsuarioCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: str
    nombre: str = Field(min_length=2, max_length=120)
    password: str
    rol: str = Field(min_length=1, max_length=30)
    # Solo para el rol Miembro: la cuenta es del alumno (mayor de edad) o de un acudiente.
    vincular_alumno_id: uuid.UUID | None = None
    vincular_acudiente_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _un_vinculo(self):
        if self.vincular_alumno_id and self.vincular_acudiente_id:
            raise ValueError("Vincula la cuenta a un alumno o a un acudiente, no a los dos.")
        return self

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
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    rol: str | None = Field(default=None, min_length=1, max_length=30)
    activo: bool | None = None
    password: str | None = None  # el SuperAdmin asigna una nueva (cierra las sesiones abiertas)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str | None) -> str | None:
        if v is not None:
            validar_politica_password(v)
        return v
