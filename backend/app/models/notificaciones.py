import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDMixin


class Notificacion(UUIDMixin, Base):
    """Un aviso para una persona. Una fila lleva todos sus canales: bandeja (si tiene cuenta), correo y WhatsApp.

    `clave` es única: generar el mismo aviso dos veces (p. ej. el worker corriendo de nuevo) no lo duplica.
    """

    __tablename__ = "notificaciones"
    __table_args__ = (
        CheckConstraint("email_estado IN ('no_aplica', 'pendiente', 'enviado', 'fallido')", name="ck_notif_email"),
        CheckConstraint(
            "whatsapp_estado IN ('no_aplica', 'pendiente', 'enviado', 'descartado')", name="ck_notif_whatsapp"
        ),
    )

    clave: Mapped[str] = mapped_column(String(200), unique=True)
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    titulo: Mapped[str] = mapped_column(String(150))
    mensaje: Mapped[str] = mapped_column(String(1000))
    alumno_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("alumnos.id"), index=True)

    # Bandeja dentro de la plataforma
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), index=True)
    leida_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Correo (lo envía el worker, con reintentos)
    email_destino: Mapped[str | None] = mapped_column(String(254))
    email_estado: Mapped[str] = mapped_column(String(12), index=True)
    email_intentos: Mapped[int] = mapped_column(Integer, default=0)
    email_error: Mapped[str | None] = mapped_column(String(255))
    email_proximo_intento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # WhatsApp (manual: el staff lo envía desde su número con un enlace wa.me)
    telefono_destino: Mapped[str | None] = mapped_column(String(20))
    whatsapp_estado: Mapped[str] = mapped_column(String(12), index=True)
    whatsapp_marcado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    whatsapp_marcado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
