import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EstadoInscripcion = Literal["pendiente_pago", "activo", "a_expulsar", "expulsado", "rechazado"]


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class InscripcionCrear(_Entrada):
    alumno_id: uuid.UUID
    # Solo Admin/SuperAdmin pueden indicar otra fecha (p. ej. para registrar inscripciones en papel).
    fecha_inscripcion: date | None = None


class PagoIn(_Entrada):
    fecha_pago: date
    monto: int = Field(gt=0, le=100_000_000)


class ProrrogaIn(_Entrada):
    nueva_fecha_limite: date
    motivo: str = Field(min_length=10, max_length=500)


class EstadoIn(_Entrada):
    estado: EstadoInscripcion
    motivo: str | None = Field(default=None, min_length=5, max_length=255)


class ProrrogaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    limite_anterior: date
    limite_nuevo: date
    motivo: str
    concedida_por: uuid.UUID
    creado_en: datetime


class AnulacionIn(_Entrada):
    motivo: str = Field(min_length=10, max_length=500)


class PagoOut(BaseModel):
    id: uuid.UUID
    fecha: date
    monto: int  # negativo si es una anulación
    anula_id: uuid.UUID | None  # abono que revierte (solo en anulaciones)
    anulado: bool  # este abono fue revertido por una anulación
    motivo: str | None
    registrado_por: uuid.UUID | None
    creado_en: datetime


class InscripcionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alumno_id: uuid.UUID
    alumno_nombre: str
    anio: int
    rama: str
    fecha_inscripcion: date
    fecha_limite_pago: date
    valor: int
    fecha_pago: date | None
    monto_pagado: int | None
    saldo: int
    estado: str
    causa_rechazo: str | None
    motivo: str | None
    prorrogas: list[ProrrogaOut]
    pagos: list[PagoOut]


class VencidasOut(BaseModel):
    vencidas: int
