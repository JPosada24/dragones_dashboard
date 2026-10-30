import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.alumnos import AlumnoCrear
from app.schemas.comunes import MotivoOpcional

EstadoInscripcion = Literal["pendiente_pago", "activo", "a_expulsar", "expulsado", "rechazado"]


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class InscripcionCrear(_Entrada):
    alumno_id: uuid.UUID
    # Solo Admin/SuperAdmin pueden indicar otra fecha (p. ej. para registrar inscripciones en papel).
    fecha_inscripcion: date | None = None


class PagoInicialIn(_Entrada):
    """Cómo paga al inscribirse: nada aún, un abono parcial (monto) o el valor completo."""

    forma: Literal["ninguno", "parcial", "completo"] = "ninguno"
    monto: int | None = Field(default=None, gt=0, le=100_000_000)

    @model_validator(mode="after")
    def _monto_si_parcial(self):
        if self.forma == "parcial" and self.monto is None:
            raise ValueError("Indica el valor del abono parcial.")
        return self


class AlumnoNuevoIn(_Entrada):
    """Alta de un alumno que entra al club: ficha + inscripción del año + primer pago, en una sola operación."""

    alumno: AlumnoCrear
    pago: PagoInicialIn = Field(default_factory=PagoInicialIn)


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
    motivo: MotivoOpcional = None


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
    causa_expulsion: str | None  # mora (la marcó el sistema) | manual
    motivo: str | None
    prorrogas: list[ProrrogaOut]
    pagos: list[PagoOut]


class VencidasOut(BaseModel):
    vencidas: int
