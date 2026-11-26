import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.schemas.comunes import (
    EstadoEquipo,
    EstadoTorneo,
    MotivoOpcional,
    OrigenEquipo,
    Rama,
    normalizar_email,
    normalizar_telefono,
)


class _Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


Sede = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


class JornadaIn(_Entrada):
    """Un día del torneo para una rama, con sus sedes (p. ej. sábado, femenina, Coliseo A y Coliseo B)."""

    rama: Rama
    fecha: date
    sedes: list[Sede] = Field(default_factory=list, max_length=6)

    @field_validator("sedes")
    @classmethod
    def _sin_repetidas(cls, v: list[str]) -> list[str]:
        if len({s.lower() for s in v}) != len(v):
            raise ValueError("Hay sedes repetidas en la jornada.")
        return v


def _validar_jornadas(jornadas: list[JornadaIn] | None) -> None:
    if jornadas and len({(j.rama, j.fecha) for j in jornadas}) != len(jornadas):
        raise ValueError("Hay dos jornadas de la misma rama el mismo día.")


class JornadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rama: Rama
    fecha: date
    sedes: list[str]


class TorneoCrear(_Entrada):
    """Con `jornadas` (una o varias: rama, día y sedes) o, en corto, con una sola `rama` (una jornada el día de
    inicio, sin sedes)."""

    nombre: str = Field(min_length=3, max_length=120)
    rama: Rama | None = None
    jornadas: list[JornadaIn] | None = Field(default=None, min_length=1, max_length=4)
    fecha_inicio: date
    fecha_fin: date
    fecha_limite_inscripcion: date
    lugar: str | None = Field(default=None, max_length=120)
    cupo_equipos: int | None = Field(default=None, ge=2, le=200)  # vacío = "cupo_equipos_sugerido"
    valor_inscripcion: int = Field(ge=0, le=100_000_000)

    @model_validator(mode="after")
    def _rama_o_jornadas(self) -> "TorneoCrear":
        if (self.rama is None) == (self.jornadas is None):
            raise ValueError("Indica la rama del torneo o sus jornadas (una de las dos).")
        _validar_jornadas(self.jornadas)
        return self


class TorneoActualizar(_Entrada):
    """Lo que se puede corregir de un torneo. El valor nuevo aplica a los equipos que se inscriban después."""

    nombre: str | None = Field(default=None, min_length=3, max_length=120)
    rama: Rama | None = None  # en corto: cambia la rama de todas las jornadas
    jornadas: list[JornadaIn] | None = Field(default=None, min_length=1, max_length=4)  # reemplaza las que hay
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    fecha_limite_inscripcion: date | None = None
    lugar: str | None = Field(default=None, max_length=120)
    cupo_equipos: int | None = Field(default=None, ge=2, le=200)
    valor_inscripcion: int | None = Field(default=None, ge=0, le=100_000_000)

    @model_validator(mode="after")
    def _no_ambas(self) -> "TorneoActualizar":
        if self.rama is not None and self.jornadas is not None:
            raise ValueError("Cambia la rama o las jornadas, no las dos a la vez.")
        _validar_jornadas(self.jornadas)
        return self


class TorneoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    rama: Rama | None  # vacía si el torneo tiene las dos ramas
    jornadas: list[JornadaOut]
    fecha_inicio: date
    fecha_fin: date
    fecha_limite_inscripcion: date
    lugar: str | None
    cupo_equipos: int
    valor_inscripcion: int
    estado: EstadoTorneo
    motivo_cancelacion: str | None
    ocupados: int
    confirmados: int
    en_espera: int
    recaudado: int
    anuncio: str | None = None  # versión del flyer (cambia con cada uno nuevo); None = sin anuncio
    anuncio_ancho: int | None = None
    anuncio_alto: int | None = None
    realizado_id: uuid.UUID | None = None  # ya se pasó a «Torneos realizados» (id de esa ficha)


class MotivoIn(_Entrada):
    motivo: MotivoOpcional = None


class EquipoCrear(_Entrada):
    nombre_club: str = Field(min_length=2, max_length=120)
    rama: Rama | None = None  # obligatoria si el torneo tiene las dos ramas
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


class SedeEquipoIn(_Entrada):
    """La sede que el organizador le asigna al equipo (una de las de su rama). Vacía = sin asignar."""

    sede: Sede | None = None


class PagoEquipoIn(_Entrada):
    monto: int = Field(gt=0, le=100_000_000)
    fecha: date


class AnularPagoEquipoIn(_Entrada):
    motivo: MotivoOpcional = None


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
    rama: Rama
    sede: str | None
    ciudad: str
    delegado_nombre: str
    delegado_telefono: str
    delegado_email: str | None
    estado: EstadoEquipo
    valor: int
    monto_pagado: int
    saldo: int
    motivo_retiro: str | None
    origen: OrigenEquipo  # staff | sitio
    pagos: list[PagoEquipoOut]


class RetiroOut(BaseModel):
    retirado: EquipoOut
    promovido: EquipoOut | None
