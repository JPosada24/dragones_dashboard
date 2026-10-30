import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comunes import MotivoOpcional


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
    motivo: MotivoOpcional = None


class AsignadosOut(BaseModel):
    asignados: int


class PagoRifaIn(_Entrada):
    monto: int = Field(gt=0, le=10_000_000)
    fecha: date


class AnularPagoRifaIn(_Entrada):
    motivo: MotivoOpcional = None


class PagoTalonarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    monto: int  # negativo si es una anulación
    anula_id: uuid.UUID | None
    motivo: str | None
    creado_en: datetime


class TalonarioOut(BaseModel):
    id: uuid.UUID
    alumno_id: uuid.UUID
    alumno_nombre: str
    rama: str
    codigo: str  # código del alumno cuando recibió el talonario (F012); sus boletas son F012-01 … F012-20
    boletas: int
    recaudado: int
    saldo: int
    pagado: bool
    pagos: list[PagoTalonarioOut]


class ActaOut(BaseModel):
    id: uuid.UUID
    rifa_id: uuid.UUID
    orden: int  # 1.ª, 2.ª… jugada de la rifa
    codigo: str  # talonario ganador (F012)
    boleta: int  # boleta dentro del talonario: la ganadora se lee F012-07
    alumno_id: uuid.UUID
    alumno_nombre: str
    rama: str
    total_participantes: int
    participantes: list[str]
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
