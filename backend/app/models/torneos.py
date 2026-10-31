import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.dominio import RAMAS, en
from app.models.mixins import TiempoMixin, UUIDMixin

ESTADOS_EQUIPO = ("pendiente_pago", "confirmado", "en_espera", "retirado")
# Estados que ocupan un lugar del cupo.
OCUPAN_CUPO = ("pendiente_pago", "confirmado")


class Torneo(UUIDMixin, TiempoMixin, Base):
    """Torneo que organiza el club. Se inscriben clubes externos (equipos), no jugadores."""

    __tablename__ = "torneos"
    __table_args__ = (
        CheckConstraint(en("rama", RAMAS), name="ck_torneos_rama"),
        CheckConstraint("estado IN ('programado', 'cancelado', 'eliminado')", name="ck_torneos_estado"),
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_torneos_fechas"),
        CheckConstraint("fecha_limite_inscripcion <= fecha_inicio", name="ck_torneos_limite"),
        CheckConstraint("cupo_equipos BETWEEN 2 AND 200", name="ck_torneos_cupo"),
        CheckConstraint("valor_inscripcion >= 0", name="ck_torneos_valor"),
    )

    nombre: Mapped[str] = mapped_column(String(120))
    rama: Mapped[str] = mapped_column(String(10))
    fecha_inicio: Mapped[date] = mapped_column(Date, index=True)
    fecha_fin: Mapped[date] = mapped_column(Date)
    fecha_limite_inscripcion: Mapped[date] = mapped_column(Date)
    lugar: Mapped[str | None] = mapped_column(String(120))
    cupo_equipos: Mapped[int] = mapped_column(Integer)
    valor_inscripcion: Mapped[int] = mapped_column(Integer)  # por equipo; se fija en cada torneo
    estado: Mapped[str] = mapped_column(String(15), default="programado")
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(255))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))


class EquipoTorneo(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "equipos_torneo"
    __table_args__ = (
        CheckConstraint(en("estado", ESTADOS_EQUIPO), name="ck_equipos_torneo_estado"),
        CheckConstraint("monto_pagado >= 0", name="ck_equipos_torneo_monto"),
        CheckConstraint("origen IN ('staff', 'sitio')", name="ck_equipos_torneo_origen"),
        # Un club no se inscribe dos veces al mismo torneo (sin importar mayúsculas), salvo que se haya retirado.
        Index(
            "ux_equipos_torneo_club", "torneo_id", text("lower(nombre_club)"), unique=True,
            postgresql_where=text("estado <> 'retirado'"),
        ),
    )

    torneo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("torneos.id"), index=True)
    nombre_club: Mapped[str] = mapped_column(String(120))
    ciudad: Mapped[str] = mapped_column(String(80))
    delegado_nombre: Mapped[str] = mapped_column(String(120))
    delegado_telefono: Mapped[str] = mapped_column(String(20))
    delegado_email: Mapped[str | None] = mapped_column(String(254))
    estado: Mapped[str] = mapped_column(String(15))
    valor: Mapped[int] = mapped_column(Integer)  # copia del valor del torneo al inscribirse
    monto_pagado: Mapped[int] = mapped_column(Integer, default=0)
    motivo_retiro: Mapped[str | None] = mapped_column(String(255))
    inscrito_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    # "staff" (desde el panel) o "sitio" (el club se inscribió solo en el sitio público).
    origen: Mapped[str] = mapped_column(String(10), default="staff", server_default=text("'staff'"))
    # Autorización de tratamiento de datos del delegado (Ley 1581 de 2012), cuando se inscribe desde el sitio.
    autoriza_datos_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    torneo: Mapped[Torneo] = relationship(lazy="joined")
    pagos: Mapped[list["PagoEquipo"]] = relationship(lazy="selectin", order_by="PagoEquipo.creado_en")

    @property
    def saldo(self) -> int:
        return self.valor - self.monto_pagado


class PagoEquipo(UUIDMixin, Base):
    """Abono de un equipo. De solo agregar (trigger); un error se revierte con una fila negativa (`anula_id`)."""

    __tablename__ = "pagos_equipo"
    __table_args__ = (
        CheckConstraint(
            "(anula_id IS NULL AND monto > 0) OR (anula_id IS NOT NULL AND monto < 0)",
            name="ck_pagos_equipo_monto",
        ),
    )

    equipo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("equipos_torneo.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[int] = mapped_column(Integer)
    anula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("pagos_equipo.id"), unique=True)
    motivo: Mapped[str | None] = mapped_column(String(500))
    registrado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
