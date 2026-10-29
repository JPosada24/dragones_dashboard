import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.comunes import Rama, normalizar_email, normalizar_telefono


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class TorneoCrear(_Entrada):
    nombre: str = Field(min_length=3, max_length=120)
    rama: Rama
    fecha_inicio: date
    fecha_fin: date
    fecha_limite_inscripcion: date
    lugar: str | None = Field(default=None, max_length=120)
    cupo_equipos: int | None = Field(default=None, ge=2, le=200)  # vacío = "cupo_equipos_sugerido"
    valor_inscripcion: int = Field(ge=0, le=100_000_000)


class TorneoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    rama: str
    fecha_inicio: date
    fecha_fin: date
    fecha_limite_inscripcion: date
    lugar: str | None
    cupo_equipos: int
    valor_inscripcion: int
    estado: str
    motivo_cancelacion: str | None
    ocupados: int
    confirmados: int
    en_espera: int
    recaudado: int


class MotivoIn(_Entrada):
    motivo: str = Field(min_length=5, max_length=255)


class EquipoCrear(_Entrada):
    nombre_club: str = Field(min_length=2, max_length=120)
    ciudad: str = Field(min_length=2, max_length=80)
    delegado_nombre: str = Field(min_length=2, max_length=120)
    delegado_telefono: str
    delegado_email: str | None = None

    @field_validator("delegado_telefono")
    @classmethod
    def _telefono(cls, v: str) -> str:
        return normalizar_telefono(v)

    @field_validator("delegado_email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return None if not v else normalizar_email(v)


class PagoEquipoIn(_Entrada):
    monto: int = Field(gt=0, le=100_000_000)
    fecha: date


class AnularPagoEquipoIn(_Entrada):
    motivo: str = Field(min_length=10, max_length=500)


class PagoEquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    monto: int
    anula_id: uuid.UUID | None
    motivo: str | None
    creado_en: datetime


class EquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre_club: str
    ciudad: str
    delegado_nombre: str
    delegado_telefono: str
    delegado_email: str | None
    estado: str
    valor: int
    monto_pagado: int
    saldo: int
    motivo_retiro: str | None
    pagos: list[PagoEquipoOut]


class RetiroOut(BaseModel):
    retirado: EquipoOut
    promovido: EquipoOut | None
