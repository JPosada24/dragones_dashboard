"""Sitio público del club: perfil, galería (álbumes y fotos), videos y equipo de trabajo.

Todo lo de aquí puede verse sin iniciar sesión cuando está publicado; nunca guarda datos privados de alumnos.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TiempoMixin, UUIDMixin


class PerfilClub(Base):
    """Una sola fila (id = 1) con los textos y contactos del sitio."""

    __tablename__ = "perfil_club"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_perfil_club_unico"),
        CheckConstraint("fundado_en BETWEEN 1900 AND 2100", name="ck_perfil_club_fundado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    nombre: Mapped[str] = mapped_column(String(120))
    lema: Mapped[str | None] = mapped_column(String(160))
    ciudad: Mapped[str | None] = mapped_column(String(80))
    sede: Mapped[str | None] = mapped_column(String(160))  # lugar de entrenamiento
    fundado_en: Mapped[int | None] = mapped_column(Integer)  # año: el sitio calcula los años del club
    # Sección «La formación va por rotaciones»: texto de entrada y 6 etapas [{titulo, texto}] (zona 1 a 6).
    # Vacío = el sitio usa sus etapas fijas.
    formacion_intro: Mapped[str | None] = mapped_column(Text)
    formacion: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    mision: Mapped[str | None] = mapped_column(Text)
    vision: Mapped[str | None] = mapped_column(Text)
    historia: Mapped[str | None] = mapped_column(Text)
    whatsapp: Mapped[str | None] = mapped_column(String(20))  # número público del club
    correo: Mapped[str | None] = mapped_column(String(254))
    instagram: Mapped[str | None] = mapped_column(String(60))  # usuario, sin @
    facebook: Mapped[str | None] = mapped_column(String(100))  # nombre de la página
    publicado: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))


class Album(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "albumes"

    nombre: Mapped[str] = mapped_column(String(120))
    fecha: Mapped[date | None] = mapped_column(Date)
    publicado: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    fotos: Mapped[list["Foto"]] = relationship(
        lazy="selectin", order_by="Foto.creado_en", cascade="all, delete-orphan", passive_deletes=True
    )


class Foto(UUIDMixin, TiempoMixin, Base):
    """Foto ya procesada: JPEG redimensionado y sin metadatos (EXIF, ubicación). Dos tamaños en el almacén."""

    __tablename__ = "fotos"

    album_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("albumes.id", ondelete="CASCADE"), index=True)
    clave: Mapped[str] = mapped_column(String(32))  # tamaño grande
    clave_miniatura: Mapped[str] = mapped_column(String(32))
    ancho: Mapped[int] = mapped_column(Integer)
    alto: Mapped[int] = mapped_column(Integer)
    # Quien la sube confirma que tiene autorización de los acudientes de los menores que aparecen.
    autorizada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))


class Video(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "videos"

    titulo: Mapped[str] = mapped_column(String(120))
    youtube_id: Mapped[str] = mapped_column(String(11))  # solo el id: el enlace se arma en el sitio
    publicado: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class IntegranteEquipo(UUIDMixin, TiempoMixin, Base):
    """Mini-perfil público de alguien del equipo de trabajo (no es una cuenta de usuario)."""

    __tablename__ = "integrantes_equipo"

    nombre: Mapped[str] = mapped_column(String(120))
    cargo: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(String(400))
    orden: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    publicado: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # Foto cuadrada (600 px, sin metadatos) en el almacén; la clave cambia con cada foto nueva.
    foto_clave: Mapped[str | None] = mapped_column(String(32))
