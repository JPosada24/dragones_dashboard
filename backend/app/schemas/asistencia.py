import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator



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
    """Sesión extra, fuera del horario semanal."""
    fecha: date


class DiaHorarioIn(_Horario):
    dia_semana: int = Field(ge=0, le=6, description="0 = lunes … 6 = domingo")


class HorarioIn(_Entrada):
    dias: list[DiaHorarioIn] = Field(max_length=7)

    @field_validator("dias")
    @classmethod
    def _sin_repetidos(cls, v: list[DiaHorarioIn]) -> list[DiaHorarioIn]:
        if len({d.dia_semana for d in v}) != len(v):
            raise ValueError("Hay un día repetido en el horario")
        return v


class DiaHorarioOut(BaseModel):
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    lugar: str | None


class HorarioOut(BaseModel):
    dias: list[DiaHorarioOut]
    dias_anticipacion: int


class HorarioActualizadoOut(HorarioOut):
    creadas: int
    eliminadas: int
    canceladas: int


class CancelarIn(_Entrada):
    motivo: str = Field(min_length=5, max_length=255)


class SesionOut(BaseModel):
    id: uuid.UUID
    fecha: date
    hora_inicio: time
    hora_fin: time
    lugar: str | None
    automatica: bool
    cancelada: bool
    causa_cancelacion: str | None
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
    rama: str
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
