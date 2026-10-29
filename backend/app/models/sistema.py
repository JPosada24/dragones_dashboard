import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, Uuid, func
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
