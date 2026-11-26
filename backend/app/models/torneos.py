import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
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
from app.models.dominio import RAMAS, en
from app.models.mixins import TiempoMixin, UUIDMixin

ESTADOS_EQUIPO = ("pendiente_pago", "confirmado", "en_espera", "retirado")
# Estados que ocupan un lugar del cupo.
OCUPAN_CUPO = ("pendiente_pago", "confirmado")
# Letras de los grupos (máximo 8 por rama).
LETRAS_GRUPO = ("A", "B", "C", "D", "E", "F", "G", "H")


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
    # La rama si todas sus jornadas son de una sola; vacía si el torneo tiene las dos (p. ej. sábado y domingo).
    rama: Mapped[str | None] = mapped_column(String(10))
    fecha_inicio: Mapped[date] = mapped_column(Date, index=True)
    fecha_fin: Mapped[date] = mapped_column(Date)
    # Hasta cuándo se inscriben los clubes desde el sitio; vacía = hasta el día de inicio. El staff inscribe hasta
    # el último día del torneo (hay equipos que llegan y pagan el mismo día).
    fecha_limite_inscripcion: Mapped[date | None] = mapped_column(Date)
    lugar: Mapped[str | None] = mapped_column(String(120))
    cupo_equipos: Mapped[int] = mapped_column(Integer)
    valor_inscripcion: Mapped[int] = mapped_column(Integer)  # por equipo; se fija en cada torneo
    estado: Mapped[str] = mapped_column(String(15), default="programado")
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(255))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    # Anuncio (flyer) para el sitio mientras tenga inscripciones abiertas: entero, en dos tamaños, sin metadatos.
    anuncio_clave: Mapped[str | None] = mapped_column(String(32))
    anuncio_mini_clave: Mapped[str | None] = mapped_column(String(32))
    anuncio_ancho: Mapped[int | None] = mapped_column(Integer)
    anuncio_alto: Mapped[int | None] = mapped_column(Integer)

    jornadas: Mapped[list["JornadaTorneo"]] = relationship(
        lazy="selectin", order_by="(JornadaTorneo.fecha, JornadaTorneo.rama)", cascade="all, delete-orphan",
    )

    @property
    def ramas(self) -> list[str]:
        return sorted({j.rama for j in self.jornadas})

    def sedes_de(self, rama: str) -> list[str]:
        """Sedes de las jornadas de esa rama."""
        return list(dict.fromkeys(s for j in self.jornadas if j.rama == rama for s in j.sedes))

    @property
    def inscripcion_hasta(self) -> date:
        """Último día en que un club se inscribe desde el sitio."""
        return self.fecha_limite_inscripcion or self.fecha_inicio


class JornadaTorneo(UUIDMixin, Base):
    """Un día del torneo para una rama, con sus sedes (p. ej. sábado femenina en dos coliseos)."""

    __tablename__ = "jornadas_torneo"
    __table_args__ = (
        CheckConstraint(en("rama", RAMAS), name="ck_jornadas_torneo_rama"),
        UniqueConstraint("torneo_id", "rama", "fecha", name="uq_jornadas_torneo_dia"),
    )

    torneo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("torneos.id", ondelete="CASCADE"), index=True)
    rama: Mapped[str] = mapped_column(String(10))
    fecha: Mapped[date] = mapped_column(Date)
    sedes: Mapped[list[str]] = mapped_column(ARRAY(String(120)), default=list, server_default=text("'{}'"))


class EquipoTorneo(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "equipos_torneo"
    __table_args__ = (
        CheckConstraint(en("estado", ESTADOS_EQUIPO), name="ck_equipos_torneo_estado"),
        CheckConstraint("monto_pagado >= 0", name="ck_equipos_torneo_monto"),
        CheckConstraint("origen IN ('staff', 'sitio')", name="ck_equipos_torneo_origen"),
        CheckConstraint(en("rama", RAMAS), name="ck_equipos_torneo_rama"),
        # Un club inscribe un equipo por rama (sin importar mayúsculas), salvo que se haya retirado.
        Index(
            "ux_equipos_torneo_club", "torneo_id", "rama", text("lower(nombre_club)"), unique=True,
            postgresql_where=text("estado <> 'retirado'"),
        ),
    )

    torneo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("torneos.id"), index=True)
    nombre_club: Mapped[str] = mapped_column(String(120))
    rama: Mapped[str] = mapped_column(String(10))
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
    # Grupo en el que quedó (sorteo de su rama) y si es cabeza de serie (en el sorteo va uno por grupo).
    grupo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("grupos_torneo.id", ondelete="SET NULL"), index=True,
    )
    cabeza_serie: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    torneo: Mapped[Torneo] = relationship(lazy="joined")
    grupo_torneo: Mapped["GrupoTorneo | None"] = relationship(lazy="joined")
    pagos: Mapped[list["PagoEquipo"]] = relationship(lazy="selectin", order_by="PagoEquipo.creado_en")

    @property
    def saldo(self) -> int:
        return self.valor - self.monto_pagado

    @property
    def grupo(self) -> str | None:
        """Letra de su grupo, si ya lo tiene."""
        return self.grupo_torneo.letra if self.grupo_torneo else None


class SorteoGrupos(UUIDMixin, Base):
    """Grupos de una rama del torneo. En borrador se vuelve a sortear cuantas veces se quiera; al confirmarlo se
    publica en el sitio y queda un acta. Después se ajusta a mano (llega un equipo, se retira otro)."""

    __tablename__ = "sorteos_grupos"
    __table_args__ = (
        CheckConstraint(en("rama", RAMAS), name="ck_sorteos_grupos_rama"),
        UniqueConstraint("torneo_id", "rama", name="uq_sorteos_grupos_rama"),
    )

    torneo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("torneos.id", ondelete="CASCADE"), index=True)
    rama: Mapped[str] = mapped_column(String(10))
    sorteado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sorteado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))

    grupos: Mapped[list["GrupoTorneo"]] = relationship(
        lazy="selectin", order_by="GrupoTorneo.letra", cascade="all, delete-orphan", back_populates="sorteo",
    )


class GrupoTorneo(UUIDMixin, Base):
    __tablename__ = "grupos_torneo"
    __table_args__ = (
        CheckConstraint(en("letra", LETRAS_GRUPO), name="ck_grupos_torneo_letra"),
        UniqueConstraint("sorteo_id", "letra", name="uq_grupos_torneo_letra"),
    )

    sorteo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sorteos_grupos.id", ondelete="CASCADE"), index=True,
    )
    letra: Mapped[str] = mapped_column(String(1))
    sede: Mapped[str | None] = mapped_column(String(120))  # opcional: una de las sedes de la jornada de la rama

    sorteo: Mapped[SorteoGrupos] = relationship(back_populates="grupos")


class ActaGrupos(UUIDMixin, Base):
    """Constancia de cada sorteo de grupos confirmado: cómo quedaron los grupos en ese momento (con el estado de
    pago de cada equipo). De solo agregar (trigger)."""

    __tablename__ = "actas_grupos"
    __table_args__ = (
        CheckConstraint(en("rama", RAMAS), name="ck_actas_grupos_rama"),
        UniqueConstraint("torneo_id", "rama", "orden", name="uq_actas_grupos_orden"),
    )

    torneo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("torneos.id"), index=True)
    rama: Mapped[str] = mapped_column(String(10))
    orden: Mapped[int] = mapped_column(Integer)  # 1.ª, 2.ª… confirmación de esa rama
    grupos: Mapped[Any] = mapped_column(JSONB)  # [{letra, sede, equipos: [{club, ciudad, cabeza_serie, estado}]}]
    huella: Mapped[str] = mapped_column(String(64))  # SHA-256 del contenido: permite verificarlo después
    confirmado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
