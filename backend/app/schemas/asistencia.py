import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.comunes import Rama


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class _Horario(_Entrada):
    hora_inicio: time
    hora_fin: time
    lugar: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _orden(self):
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        return self


class SesionCrear(_Horario):
    rama: Rama
    fecha: date


class SesionProgramar(_Horario):
    rama: Rama
    desde: date
    hasta: date
    dias_semana: list[int] = Field(min_length=1, max_length=7, description="0 = lunes … 6 = domingo")

    @field_validator("dias_semana")
    @classmethod
    def _dias(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v) or len(set(v)) != len(v):
            raise ValueError("Días de la semana inválidos (0 = lunes … 6 = domingo, sin repetir)")
        return v


class CancelarIn(_Entrada):
    motivo: str = Field(min_length=5, max_length=255)


class SesionOut(BaseModel):
    id: uuid.UUID
    rama: str
    fecha: date
    hora_inicio: time
    hora_fin: time
    lugar: str | None
    cancelada: bool
    motivo_cancelacion: str | None
    cerrada: bool


class MarcaIn(_Entrada):
    alumno_id: uuid.UUID
    estado: Literal["presente", "ausente"]


class MarcarGrupoIn(_Entrada):
    marcas: list[MarcaIn] = Field(min_length=1, max_length=200)

    @field_validator("marcas")
    @classmethod
    def _sin_repetidos(cls, v: list[MarcaIn]) -> list[MarcaIn]:
        if len({m.alumno_id for m in v}) != len(v):
            raise ValueError("Un alumno aparece más de una vez")
        return v


class MarcarPropiaIn(_Entrada):
    alumno_id: uuid.UUID


class CorreccionIn(_Entrada):
    estado: Literal["presente", "ausente", "justificado"]
    motivo: str = Field(min_length=10, max_length=255)


class FilaPlanillaOut(BaseModel):
    alumno_id: uuid.UUID
    alumno_nombre: str
    asistencia: str | None
    justificacion: str | None
    multa: str | None


class JustificarIn(_Entrada):
    alumno_id: uuid.UUID
    motivo: str = Field(min_length=10, max_length=500)


class RevisarIn(_Entrada):
    aprobar: bool
    comentario: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _comentario_si_rechaza(self):
        if not self.aprobar and not self.comentario:
            raise ValueError("Al rechazar una justificación indica el motivo en 'comentario'")
        return self


class JustificacionOut(BaseModel):
    id: uuid.UUID
    sesion_id: uuid.UUID
    fecha_sesion: date
    rama: str
    alumno_id: uuid.UUID
    alumno_nombre: str
    motivo: str
    estado: str
    comentario: str | None
    creado_en: datetime
    revisada_en: datetime | None


class CierreOut(BaseModel):
    sesiones: int
    ausencias: int
    multas: int


class AlertaOut(BaseModel):
    alumno_id: uuid.UUID
    alumno_nombre: str
    rama: str
    inasistencias_seguidas: int


class MultaOut(BaseModel):
    id: uuid.UUID
    alumno_id: uuid.UUID
    alumno_nombre: str
    sesion_id: uuid.UUID
    fecha_sesion: date
    valor: int
    estado: str
    fecha_pago: date | None
    motivo_anulacion: str | None


class MultaPagoIn(_Entrada):
    fecha_pago: date


class MultaAnularIn(_Entrada):
    motivo: str = Field(min_length=10, max_length=255)
