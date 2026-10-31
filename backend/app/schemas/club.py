import re
import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.comunes import normalizar_email, normalizar_telefono
from app.schemas.torneos import EquipoCrear

_USUARIO_RED = re.compile(r"^[A-Za-z0-9._-]{1,60}$")


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _texto(maximo: int):
    return Field(default=None, max_length=maximo)


# ---------- Panel (club.editar) ----------
class PerfilIn(_Entrada):
    """Cambios al perfil. Solo se aplican los campos enviados; vacío = borrar el dato."""

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    lema: str | None = _texto(160)
    ciudad: str | None = _texto(80)
    sede: str | None = _texto(160)
    mision: str | None = _texto(2000)
    vision: str | None = _texto(2000)
    historia: str | None = _texto(4000)
    whatsapp: str | None = None
    correo: str | None = None
    instagram: str | None = None
    facebook: str | None = None
    publicado: bool | None = None

    @field_validator("lema", "ciudad", "sede", "mision", "vision", "historia")
    @classmethod
    def _vacio(cls, v: str | None) -> str | None:
        return v or None

    @field_validator("whatsapp")
    @classmethod
    def _whatsapp(cls, v: str | None) -> str | None:
        return normalizar_telefono(v) if v else None

    @field_validator("correo")
    @classmethod
    def _correo(cls, v: str | None) -> str | None:
        return normalizar_email(v) if v else None

    @field_validator("instagram", "facebook")
    @classmethod
    def _red(cls, v: str | None) -> str | None:
        """Solo el usuario de la red (sin @ ni enlace): el sitio arma el enlace, así no se cuela un dominio ajeno."""
        if not v:
            return None
        v = v.removeprefix("@").rstrip("/").split("/")[-1]
        if not _USUARIO_RED.match(v):
            raise ValueError("Escribe solo el usuario de la red social (letras, números, punto, guion o _).")
        return v


class PerfilOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nombre: str
    lema: str | None
    ciudad: str | None
    sede: str | None
    mision: str | None
    vision: str | None
    historia: str | None
    whatsapp: str | None
    correo: str | None
    instagram: str | None
    facebook: str | None
    publicado: bool


class AlbumIn(_Entrada):
    nombre: str = Field(min_length=2, max_length=120)
    fecha: date | None = None
    publicado: bool = False


class AlbumCambios(_Entrada):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    fecha: date | None = None
    publicado: bool | None = None


class FotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ancho: int
    alto: int


class AlbumOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    fecha: date | None
    publicado: bool
    fotos: list[FotoOut]


class VideoIn(_Entrada):
    titulo: str = Field(min_length=2, max_length=120)
    enlace: str = Field(min_length=10, max_length=300)
    publicado: bool = True


class VideoCambios(_Entrada):
    titulo: str | None = Field(default=None, min_length=2, max_length=120)
    publicado: bool | None = None


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titulo: str
    youtube_id: str
    publicado: bool


class IntegranteIn(_Entrada):
    nombre: str = Field(min_length=2, max_length=120)
    cargo: str = Field(min_length=2, max_length=120)
    bio: str | None = Field(default=None, max_length=400)
    orden: int = Field(default=0, ge=0, le=999)
    publicado: bool = True


class IntegranteCambios(_Entrada):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    cargo: str | None = Field(default=None, min_length=2, max_length=120)
    bio: str | None = Field(default=None, max_length=400)
    orden: int | None = Field(default=None, ge=0, le=999)
    publicado: bool | None = None


class IntegranteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    cargo: str
    bio: str | None
    orden: int
    publicado: bool


class ClubPanelOut(BaseModel):
    perfil: PerfilOut
    albumes: list[AlbumOut]
    videos: list[VideoOut]
    equipo: list[IntegranteOut]


# ---------- Sitio público (sin sesión) ----------
class HorarioPublicoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dia_semana: int
    hora_inicio: time
    hora_fin: time
    lugar: str | None


class TorneoPublicoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    rama: str
    fecha_inicio: date
    fecha_fin: date
    fecha_limite_inscripcion: date
    lugar: str | None
    valor_inscripcion: int
    cupos_libres: int


class SitioOut(BaseModel):
    perfil: PerfilOut
    horario: list[HorarioPublicoOut]
    albumes: list[AlbumOut]
    videos: list[VideoOut]
    equipo: list[IntegranteOut]
    torneos: list[TorneoPublicoOut]


class InscripcionSitioIn(EquipoCrear):
    """Formulario público de inscripción de un club a un torneo."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    acepta_datos: Literal[True]  # autorización de tratamiento de datos (Ley 1581 de 2012)
    # Trampa para bots: el formulario lo oculta, así que una persona nunca lo llena.
    sitio_web: str | None = Field(default=None, max_length=200)


class InscripcionSitioOut(BaseModel):
    estado: str  # pendiente_pago | en_espera | confirmado
    valor: int
    mensaje: str
    registrado_en: datetime | None = None
