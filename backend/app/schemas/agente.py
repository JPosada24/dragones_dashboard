from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MensajeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rol: Literal["user", "assistant"]
    texto: str = Field(min_length=1, max_length=6000)


class PreguntaIn(BaseModel):
    """Pregunta al asistente. El historial lo guarda el navegador (solo texto) y se reenvía en cada pregunta."""

    model_config = ConfigDict(extra="forbid")

    pregunta: str = Field(min_length=1, max_length=2000)
    historial: list[MensajeIn] = Field(default_factory=list, max_length=20)

    @field_validator("historial")
    @classmethod
    def _empieza_por_usuario(cls, v: list[MensajeIn]) -> list[MensajeIn]:
        if v and v[0].rol != "user":
            raise ValueError("El historial debe empezar con un mensaje del usuario")
        return v


class RespuestaOut(BaseModel):
    texto: str
    herramientas: list[str]
    restantes_hoy: int


class EstadoAgenteOut(BaseModel):
    configurado: bool
    limite_diario: int
    usados_hoy: int
