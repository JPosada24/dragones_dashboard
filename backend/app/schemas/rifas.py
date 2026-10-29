import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.comunes import normalizar_telefono


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class RifaCrear(_Entrada):
    nombre: str = Field(min_length=3, max_length=120)
    anio: int = Field(ge=2000, le=2100)
    premio: str = Field(min_length=3, max_length=255)
    fecha_sorteo: date


class RifaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    anio: int
    numero: int
    premio: str
    fecha_sorteo: date
    puestos_por_talonario: int
    precio_puesto: int
    valor_talonario: int
    estado: str
    motivo_cancelacion: str | None
    talonarios: int
    talonarios_pagados: int
    recaudado: int
    esperado: int


class CancelarRifaIn(_Entrada):
    motivo: str = Field(min_length=5, max_length=255)


class AsignadosOut(BaseModel):
    asignados: int


class CompradorIn(_Entrada):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    telefono: str | None = None

    @field_validator("telefono")
    @classmethod
    def _telefono(cls, v: str | None) -> str | None:
        return None if not v else normalizar_telefono(v)


class PagoRifaIn(_Entrada):
    monto: int = Field(gt=0, le=10_000_000)
    fecha: date


class AnularPagoRifaIn(_Entrada):
    motivo: str = Field(min_length=10, max_length=500)


class PagoPuestoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    monto: int
    anula_id: uuid.UUID | None
    motivo: str | None
    creado_en: datetime


class PuestoOut(BaseModel):
    numero: int
    comprador_nombre: str | None
    comprador_telefono: str | None
    monto_pagado: int
    saldo: int
    pagos: list[PagoPuestoOut]


class TalonarioOut(BaseModel):
    id: uuid.UUID
    alumno_id: uuid.UUID
    alumno_nombre: str
    rama: str
    desde: int
    hasta: int
    recaudado: int
    saldo: int
    pagado: bool
    puestos: list[PuestoOut]


class ActaOut(BaseModel):
    rifa_id: uuid.UUID
    numero_ganador: int
    alumno_id: uuid.UUID
    alumno_nombre: str
    comprador_nombre: str | None
    total_participantes: int
    participantes: list[int]
    huella: str
    jugado_en: datetime


class DeudaRifaOut(BaseModel):
    rifa: str
    saldo: int


class EstadoCuentaOut(BaseModel):
    alumno_id: uuid.UUID
    anio: int
    inscripcion_estado: str | None
    inscripcion_saldo: int
    multas_pendientes: int
    multas_saldo: int
    rifas: list[DeudaRifaOut]
    total: int
    al_dia: bool
    en_mora: bool
    entra_en_mora: date | None
