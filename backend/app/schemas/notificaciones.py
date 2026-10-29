import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: str
    titulo: str
    mensaje: str
    alumno_id: uuid.UUID | None
    leida: bool
    creado_en: datetime


class WhatsAppOut(BaseModel):
    id: uuid.UUID
    tipo: str
    titulo: str
    telefono: str
    mensaje: str
    enlace: str  # https://wa.me/... abre WhatsApp con el mensaje listo
    creado_en: datetime


class MarcarWhatsAppIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accion: Literal["enviado", "descartado"]


class CorreoEstadoOut(BaseModel):
    id: uuid.UUID
    tipo: str
    titulo: str
    email: str  # enmascarado
    estado: str
    intentos: int
    error: str | None
    creado_en: datetime


class ResultadoPruebaOut(BaseModel):
    enviado: bool
    modo: str
    detalle: str


class ConteoOut(BaseModel):
    marcadas: int
