"""Solicitudes de los titulares sobre sus datos personales (Ley 1581): consultas y reclamos."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDMixin


class SolicitudDatos(UUIDMixin, Base):
    __tablename__ = "solicitudes_datos"
    __table_args__ = (
        CheckConstraint("tipo IN ('consulta', 'reclamo')", name="ck_solicitudes_datos_tipo"),
        CheckConstraint("estado IN ('en_tramite', 'respondida')", name="ck_solicitudes_datos_estado"),
        CheckConstraint("(estado = 'respondida') = (respuesta IS NOT NULL)", name="ck_solicitudes_datos_respuesta"),
        Index("ix_solicitudes_datos_estado", "estado", "vence_el"),
    )

    tipo: Mapped[str] = mapped_column(String(10))  # consulta: 10 días hábiles; reclamo: 15
    titular: Mapped[str] = mapped_column(String(120))  # quien la hace (titular o acudiente)
    contacto: Mapped[str] = mapped_column(String(120))  # correo o teléfono para responder
    descripcion: Mapped[str] = mapped_column(Text)
    recibida_el: Mapped[date] = mapped_column(Date)
    vence_el: Mapped[date] = mapped_column(Date)
    prorrogada: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    motivo_prorroga: Mapped[str | None] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(12), server_default=text("'en_tramite'"))
    respuesta: Mapped[str | None] = mapped_column(Text)
    respondida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registrada_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
