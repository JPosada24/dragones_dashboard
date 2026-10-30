import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.alumnos import Alumno
from app.models.mixins import TiempoMixin, UUIDMixin

# Estados en los que la rifa no cuenta (ni deuda, ni paz y salvo, ni el máximo por año).
RIFA_FUERA = ("cancelada", "eliminada")


class Rifa(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "rifas"
    __table_args__ = (
        CheckConstraint("estado IN ('abierta', 'sorteada', 'cancelada', 'eliminada')", name="ck_rifas_estado"),
        CheckConstraint("numero >= 1", name="ck_rifas_numero"),
        CheckConstraint("puestos_por_talonario BETWEEN 1 AND 100", name="ck_rifas_puestos"),
        CheckConstraint("precio_puesto > 0", name="ck_rifas_precio"),
        # Una eliminada libera su número (no aparece en ninguna parte).
        Index("uq_rifas_anio_numero", "anio", "numero", unique=True, postgresql_where=text("estado <> 'eliminada'")),
    )

    nombre: Mapped[str] = mapped_column(String(120))
    anio: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(Integer)  # 1.ª, 2.ª… rifa del año
    premio: Mapped[str] = mapped_column(String(255))
    fecha_sorteo: Mapped[date] = mapped_column(Date)
    # Copiados de "configuracion" al crearla: cambiar la configuración no altera rifas en curso.
    # "puestos" = boletas de cada talonario (F012-01 … F012-20).
    puestos_por_talonario: Mapped[int] = mapped_column(Integer)
    precio_puesto: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(15), default="abierta")
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(255))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))

    @property
    def valor_talonario(self) -> int:
        return self.puestos_por_talonario * self.precio_puesto


class Talonario(UUIDMixin, TiempoMixin, Base):
    """El talonario de un alumno en una rifa. Sus boletas son código-1 … código-N (F012-01 … F012-20)."""

    __tablename__ = "talonarios"
    __table_args__ = (
        UniqueConstraint("rifa_id", "alumno_id", name="uq_talonarios_rifa_alumno"),
        UniqueConstraint("rifa_id", "indice", name="uq_talonarios_rifa_indice"),
    )

    rifa_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("rifas.id"), index=True)
    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id"), index=True)
    indice: Mapped[int] = mapped_column(Integer)  # orden de entrega dentro de la rifa
    # Código del alumno al entregarle el talonario (no cambia aunque luego se corrija su rama).
    codigo: Mapped[str] = mapped_column(String(8))

    rifa: Mapped[Rifa] = relationship(lazy="joined")
    alumno: Mapped[Alumno] = relationship(lazy="joined")
    pagos: Mapped[list["PagoTalonario"]] = relationship(lazy="selectin", order_by="PagoTalonario.creado_en")

    @property
    def recaudado(self) -> int:
        return sum(p.monto for p in self.pagos)

    @property
    def saldo(self) -> int:
        return self.rifa.valor_talonario - self.recaudado

    @property
    def pagado(self) -> bool:
        """Paz y salvo de la rifa: el talonario pagado al 100 % (todas sus boletas entran al sorteo)."""
        return self.recaudado >= self.rifa.valor_talonario

    def boletas(self) -> list[str]:
        return [boleta(self.codigo, n) for n in range(1, self.rifa.puestos_por_talonario + 1)]


def boleta(codigo: str, numero: int) -> str:
    """F012-07: boleta 7 del talonario de F012."""
    return f"{codigo}-{numero:02d}"


class PagoTalonario(UUIDMixin, Base):
    """Pago (o abono) de un talonario. De solo agregar (trigger); un error se revierte con una fila negativa."""

    __tablename__ = "pagos_talonario"
    __table_args__ = (
        CheckConstraint(
            "(anula_id IS NULL AND monto > 0) OR (anula_id IS NOT NULL AND monto < 0)", name="ck_pagos_talonario_monto",
        ),
    )

    talonario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("talonarios.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[int] = mapped_column(Integer)
    anula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("pagos_talonario.id"), unique=True)
    motivo: Mapped[str | None] = mapped_column(String(500))
    registrado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ActaSorteo(UUIDMixin, Base):
    """Constancia de cada jugada del sorteo (una rifa puede jugarse varias veces). De solo agregar (trigger)."""

    __tablename__ = "actas_sorteo"
    __table_args__ = (
        UniqueConstraint("rifa_id", "orden", name="uq_actas_rifa_orden"),
        # Una boleta no gana dos veces en la misma rifa.
        UniqueConstraint("rifa_id", "codigo", "boleta", name="uq_actas_rifa_boleta"),
    )

    rifa_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("rifas.id"), index=True)
    orden: Mapped[int] = mapped_column(Integer)  # 1.ª, 2.ª… jugada
    talonario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("talonarios.id"))
    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id"))  # dueño del talonario
    codigo: Mapped[str] = mapped_column(String(8))
    boleta: Mapped[int] = mapped_column(Integer)
    participantes: Mapped[Any] = mapped_column(JSONB)  # lista ordenada de las boletas en la urna ("F001-01"…)
    total_participantes: Mapped[int] = mapped_column(Integer)
    huella: Mapped[str] = mapped_column(String(64))  # SHA-256 de la lista: permite verificarla después
    jugado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    jugado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
