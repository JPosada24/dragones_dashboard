import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Time, UniqueConstraint, Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.alumnos import Alumno
from app.models.dominio import (
    ESTADOS_ASISTENCIA, ESTADOS_JUSTIFICACION, ESTADOS_MULTA, ORIGENES_ASISTENCIA, RAMAS, en,
)
from app.models.mixins import TiempoMixin, UUIDMixin


class Sesion(UUIDMixin, TiempoMixin, Base):
    """Un entrenamiento de una rama en una fecha. Al cierre del día se generan ausencias y multas."""

    __tablename__ = "sesiones"
    __table_args__ = (
        CheckConstraint(en("rama", RAMAS), name="ck_sesiones_rama"),
        CheckConstraint("hora_fin > hora_inicio", name="ck_sesiones_horario"),
        UniqueConstraint("rama", "fecha", "hora_inicio", name="uq_sesiones_rama_fecha_hora"),
    )

    rama: Mapped[str] = mapped_column(String(10))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    lugar: Mapped[str | None] = mapped_column(String(120))
    cancelada: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(255))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))


class Asistencia(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "asistencias"
    __table_args__ = (
        CheckConstraint(en("estado", ESTADOS_ASISTENCIA), name="ck_asistencias_estado"),
        CheckConstraint(en("origen", ORIGENES_ASISTENCIA), name="ck_asistencias_origen"),
        UniqueConstraint("sesion_id", "alumno_id", name="uq_asistencias_sesion_alumno"),
    )

    sesion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sesiones.id"))
    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id"), index=True)
    estado: Mapped[str] = mapped_column(String(15))
    origen: Mapped[str] = mapped_column(String(15))
    marcado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))

    alumno: Mapped[Alumno] = relationship(lazy="joined")


class Justificacion(UUIDMixin, Base):
    __tablename__ = "justificaciones"
    __table_args__ = (
        CheckConstraint(en("estado", ESTADOS_JUSTIFICACION), name="ck_justificaciones_estado"),
        # Una sola justificación "viva" (pendiente o aprobada) por alumno y sesión; las rechazadas quedan de historial.
        Index(
            "ux_justificaciones_viva", "sesion_id", "alumno_id", unique=True,
            postgresql_where=text("estado IN ('pendiente', 'aprobada')"),
        ),
    )

    sesion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sesiones.id"), index=True)
    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id"), index=True)
    motivo: Mapped[str] = mapped_column(String(500))
    estado: Mapped[str] = mapped_column(String(15), default="pendiente")
    creada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    revisada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    revisada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comentario: Mapped[str | None] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    sesion: Mapped[Sesion] = relationship(lazy="joined")
    alumno: Mapped[Alumno] = relationship(lazy="joined")


class Multa(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "multas"
    __table_args__ = (
        CheckConstraint(en("estado", ESTADOS_MULTA), name="ck_multas_estado"),
        CheckConstraint("valor > 0", name="ck_multas_valor"),
        # Una inasistencia genera como mucho una multa vigente; una anulada no impide generar otra si se corrige.
        Index(
            "ux_multas_vigente", "alumno_id", "sesion_id", unique=True,
            postgresql_where=text("estado IN ('pendiente', 'pagada')"),
        ),
    )

    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id"), index=True)
    sesion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sesiones.id"))
    valor: Mapped[int] = mapped_column(Integer)  # se copia de "configuracion" al generarla
    estado: Mapped[str] = mapped_column(String(15), index=True, default="pendiente")
    fecha_pago: Mapped[date | None] = mapped_column(Date)
    pago_registrado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(String(255))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))

    sesion: Mapped[Sesion] = relationship(lazy="joined")
    alumno: Mapped[Alumno] = relationship(lazy="joined")
