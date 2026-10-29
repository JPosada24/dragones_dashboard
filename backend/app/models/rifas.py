import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.alumnos import Alumno
from app.models.mixins import TiempoMixin, UUIDMixin


class Rifa(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "rifas"
    __table_args__ = (
        CheckConstraint("estado IN ('abierta', 'sorteada', 'cancelada')", name="ck_rifas_estado"),
        CheckConstraint("numero >= 1", name="ck_rifas_numero"),
        CheckConstraint("puestos_por_talonario BETWEEN 1 AND 100", name="ck_rifas_puestos"),
        CheckConstraint("precio_puesto > 0", name="ck_rifas_precio"),
        UniqueConstraint("anio", "numero", name="uq_rifas_anio_numero"),
    )

    nombre: Mapped[str] = mapped_column(String(120))
    anio: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(Integer)  # 1.ª, 2.ª… rifa del año
    premio: Mapped[str] = mapped_column(String(255))
    fecha_sorteo: Mapped[date] = mapped_column(Date)
    # Copiados de "configuracion" al crearla: cambiar la configuración no altera rifas en curso.
    puestos_por_talonario: Mapped[int] = mapped_column(Integer)
    precio_puesto: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(15), default="abierta")
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(255))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))

    @property
    def valor_talonario(self) -> int:
        return self.puestos_por_talonario * self.precio_puesto


class Talonario(UUIDMixin, TiempoMixin, Base):
    """El talonario de un alumno en una rifa. Sus puestos van del indice*N al indice*N + N - 1."""

    __tablename__ = "talonarios"
    __table_args__ = (
        UniqueConstraint("rifa_id", "alumno_id", name="uq_talonarios_rifa_alumno"),
        UniqueConstraint("rifa_id", "indice", name="uq_talonarios_rifa_indice"),
    )

    rifa_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("rifas.id"), index=True)
    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id"), index=True)
    indice: Mapped[int] = mapped_column(Integer)

    rifa: Mapped[Rifa] = relationship(lazy="joined")
    alumno: Mapped[Alumno] = relationship(lazy="joined")
    puestos: Mapped[list["Puesto"]] = relationship(lazy="selectin", order_by="Puesto.numero")

    @property
    def recaudado(self) -> int:
        return sum(p.monto_pagado for p in self.puestos)

    @property
    def saldo(self) -> int:
        return self.rifa.valor_talonario - self.recaudado

    @property
    def pagado(self) -> bool:
        """Paz y salvo de la rifa: todos los puestos pagados al 100 %."""
        return all(p.monto_pagado >= self.rifa.precio_puesto for p in self.puestos)


class Puesto(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "puestos"
    __table_args__ = (
        UniqueConstraint("rifa_id", "numero", name="uq_puestos_rifa_numero"),
        CheckConstraint("monto_pagado >= 0", name="ck_puestos_monto"),
    )

    rifa_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("rifas.id"))
    talonario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("talonarios.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    comprador_nombre: Mapped[str | None] = mapped_column(String(120))
    comprador_telefono: Mapped[str | None] = mapped_column(String(20))
    monto_pagado: Mapped[int] = mapped_column(Integer, default=0)  # suma de sus pagos (incluye anulaciones)

    pagos: Mapped[list["PagoPuesto"]] = relationship(lazy="selectin", order_by="PagoPuesto.creado_en")


class PagoPuesto(UUIDMixin, Base):
    """Pago de un puesto. De solo agregar (trigger); un error se revierte con una fila negativa (`anula_id`)."""

    __tablename__ = "pagos_puesto"
    __table_args__ = (
        CheckConstraint(
            "(anula_id IS NULL AND monto > 0) OR (anula_id IS NOT NULL AND monto < 0 AND motivo IS NOT NULL)",
            name="ck_pagos_puesto_monto",
        ),
    )

    puesto_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("puestos.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[int] = mapped_column(Integer)
    anula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("pagos_puesto.id"), unique=True)
    motivo: Mapped[str | None] = mapped_column(String(500))
    registrado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ActaSorteo(UUIDMixin, Base):
    """Constancia del sorteo. De solo agregar (trigger): nadie puede cambiar el resultado después."""

    __tablename__ = "actas_sorteo"

    rifa_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("rifas.id"), unique=True)
    numero_ganador: Mapped[int] = mapped_column(Integer)
    puesto_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("puestos.id"))
    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id"))  # quien vendió el puesto
    comprador_nombre: Mapped[str | None] = mapped_column(String(120))  # copia: no cambia si se edita el puesto
    participantes: Mapped[Any] = mapped_column(JSONB)  # lista ordenada de los números que entraron al sorteo
    total_participantes: Mapped[int] = mapped_column(Integer)
    huella: Mapped[str] = mapped_column(String(64))  # SHA-256 de la lista: permite verificarla después
    jugado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    jugado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
