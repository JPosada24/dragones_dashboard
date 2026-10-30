import uuid
from datetime import date, datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.fechas import hoy
from app.schemas.comunes import Rama, TipoDocumento, normalizar_documento, normalizar_email, normalizar_telefono

TipoArchivo = Literal["identidad", "eps", "consentimiento", "certificado_medico", "foto", "otro"]


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("documento", check_fields=False)
    @classmethod
    def _documento(cls, v: str | None) -> str | None:
        return None if v is None else normalizar_documento(v)

    @field_validator("email", check_fields=False)
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return None if not v else normalizar_email(v)

    @field_validator("telefono", check_fields=False)
    @classmethod
    def _telefono(cls, v: str | None) -> str | None:
        return None if not v else normalizar_telefono(v)

    @field_validator("fecha_nacimiento", check_fields=False)
    @classmethod
    def _nacimiento(cls, v: date | None) -> date | None:
        if v is not None and not (date(1900, 1, 1) <= v <= hoy()):  # hoy en Bogotá, no en la zona del servidor
            raise ValueError("Fecha de nacimiento inválida")
        return v


class _SinNulos(_Entrada):
    """En un PATCH, omitir un campo es "no cambiarlo"; mandarlo en null solo vale para los opcionales."""

    OBLIGATORIOS: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _no_nulos(self):
        for campo in self.OBLIGATORIOS:
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"'{campo}' no puede ser nulo")
        return self


# ---------- Acudientes ----------
class AcudienteCrear(_Entrada):
    nombres: str = Field(min_length=2, max_length=80)
    apellidos: str = Field(min_length=2, max_length=80)
    tipo_documento: TipoDocumento
    documento: str
    telefono: str
    email: str | None = None
    usuario_id: uuid.UUID | None = None


class AcudienteActualizar(_SinNulos):
    OBLIGATORIOS: ClassVar[tuple[str, ...]] = ("nombres", "apellidos", "tipo_documento", "documento", "telefono")

    nombres: str | None = Field(default=None, min_length=2, max_length=80)
    apellidos: str | None = Field(default=None, min_length=2, max_length=80)
    tipo_documento: TipoDocumento | None = None
    documento: str | None = None
    telefono: str | None = None
    email: str | None = None
    usuario_id: uuid.UUID | None = None


class AcudienteOut(BaseModel):
    id: uuid.UUID
    nombres: str
    apellidos: str
    tipo_documento: str
    documento: str  # enmascarado: ****1234
    telefono: str
    email: str | None
    usuario_id: uuid.UUID | None


# ---------- Alumnos ----------
class VinculoIn(_Entrada):
    acudiente_id: uuid.UUID
    parentesco: str = Field(min_length=2, max_length=30)
    principal: bool = False


class AlumnoCrear(_Entrada):
    nombres: str = Field(min_length=2, max_length=80)
    apellidos: str = Field(min_length=2, max_length=80)
    tipo_documento: TipoDocumento
    documento: str
    fecha_nacimiento: date
    rama: Rama
    telefono: str | None = None
    email: str | None = None
    direccion: str | None = Field(default=None, max_length=200)
    eps: str | None = Field(default=None, max_length=80)
    usuario_id: uuid.UUID | None = None
    acudientes: list[VinculoIn] = Field(default_factory=list, max_length=5)


class AlumnoActualizar(_SinNulos):
    OBLIGATORIOS: ClassVar[tuple[str, ...]] = (
        "nombres", "apellidos", "tipo_documento", "documento", "fecha_nacimiento", "rama", "activo",
    )

    nombres: str | None = Field(default=None, min_length=2, max_length=80)
    apellidos: str | None = Field(default=None, min_length=2, max_length=80)
    tipo_documento: TipoDocumento | None = None
    documento: str | None = None
    fecha_nacimiento: date | None = None
    rama: Rama | None = None
    telefono: str | None = None
    email: str | None = None
    direccion: str | None = Field(default=None, max_length=200)
    eps: str | None = Field(default=None, max_length=80)
    usuario_id: uuid.UUID | None = None
    activo: bool | None = None


class AcudienteVinculadoOut(BaseModel):
    acudiente_id: uuid.UUID
    nombres: str
    apellidos: str
    telefono: str
    parentesco: str
    principal: bool


class AlumnoOut(BaseModel):
    id: uuid.UUID
    nombres: str
    apellidos: str
    tipo_documento: str
    documento: str  # enmascarado: ****1234
    fecha_nacimiento: date
    edad: int
    es_menor: bool
    rama: str
    telefono: str | None
    email: str | None
    direccion: str | None
    eps: str | None
    usuario_id: uuid.UUID | None
    activo: bool
    inscripcion_estado: str | None  # del año en curso
    acudientes: list[AcudienteVinculadoOut]


class DocumentoIdentidadOut(BaseModel):
    tipo_documento: str
    documento: str


# ---------- Documentos ----------
class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: str
    nombre_original: str
    mime: str
    tamano: int
    creado_en: datetime
