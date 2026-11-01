"""Solicitudes de habeas data."""
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoSolicitud = Literal["consulta", "reclamo"]
EstadoSolicitud = Literal["en_tramite", "respondida"]


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class SolicitudIn(_Entrada):
    tipo: TipoSolicitud
    titular: str = Field(min_length=3, max_length=120)
    contacto: str = Field(min_length=5, max_length=120)
    descripcion: str = Field(min_length=10, max_length=2000)
    recibida_el: date | None = None  # vacía = hoy (la ley cuenta desde que se recibe)


class RespuestaIn(_Entrada):
    respuesta: str = Field(min_length=10, max_length=4000)


class ProrrogaSolicitudIn(_Entrada):
    motivo: str = Field(min_length=10, max_length=500)


class SolicitudOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: TipoSolicitud
    titular: str
    contacto: str
    descripcion: str
    recibida_el: date
    vence_el: date
    dias_habiles_restantes: int  # negativo = vencida
    prorrogada: bool
    motivo_prorroga: str | None
    estado: EstadoSolicitud
    respuesta: str | None
    respondida_en: datetime | None
