import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Configuracion(Base):
    """Parámetros editables del club (multa, plazos, políticas...)."""

    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[Any] = mapped_column(JSONB)
    descripcion: Mapped[str | None] = mapped_column(String(255))
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))


class Auditoria(Base):
    """Bitácora de solo agregar: en PostgreSQL un trigger impide UPDATE y DELETE."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), index=True)
    accion: Mapped[str] = mapped_column(String(80), index=True)
    entidad: Mapped[str] = mapped_column(String(60))
    entidad_id: Mapped[str | None] = mapped_column(String(64))
    antes: Mapped[Any | None] = mapped_column(JSONB)
    despues: Mapped[Any | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UsoAgente(Base):
    """Una fila por pregunta al asistente de IA: sirve para el límite diario y para estimar el gasto.

    No guarda la pregunta ni la respuesta (pueden traer datos de menores); solo cifras y herramientas usadas.
    """

    __tablename__ = "uso_agente"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    tokens_entrada: Mapped[int] = mapped_column(Integer)
    tokens_salida: Mapped[int] = mapped_column(Integer)
    tokens_cache: Mapped[int] = mapped_column(Integer)
    herramientas: Mapped[Any] = mapped_column(JSONB, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
