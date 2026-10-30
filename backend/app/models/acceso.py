import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.dominio import RAMAS, en
from app.models.mixins import TiempoMixin, UUIDMixin

roles_permisos = Table(
    "roles_permisos",
    Base.metadata,
    Column("rol_id", Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permiso_id", Uuid, ForeignKey("permisos.id", ondelete="CASCADE"), primary_key=True),
)


class Permiso(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "permisos"

    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    descripcion: Mapped[str] = mapped_column(String(255))


class Rol(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "roles"

    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(60))
    descripcion: Mapped[str | None] = mapped_column(String(255))
    permisos: Mapped[list[Permiso]] = relationship(secondary=roles_permisos, lazy="selectin")


class Usuario(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint(f"rama IS NULL OR {en('rama', RAMAS)}", name="ck_usuarios_rama"),)

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    rol_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Va dentro del token de acceso; sube al cambiar la contraseña o el rol y los tokens anteriores dejan de valer.
    credenciales_version: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Rama del Entrenador: limita qué alumnos ve con "alumnos.ver_rama".
    rama: Mapped[str | None] = mapped_column(String(10))

    rol: Mapped[Rol] = relationship(lazy="joined")

    @property
    def permisos_codigos(self) -> list[str]:
        return sorted(p.codigo for p in self.rol.permisos)


class SesionRefresh(UUIDMixin, TiempoMixin, Base):
    """Un refresh token emitido. Se rota en cada uso; la 'familia' agrupa la cadena de rotaciones."""

    __tablename__ = "sesiones_refresh"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    familia_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(45))
