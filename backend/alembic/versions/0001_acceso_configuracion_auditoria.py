"""Acceso (usuarios, roles, permisos, sesiones), configuración y auditoría

Revision ID: 0001
Revises:
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _tiempos() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "permisos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("codigo", sa.String(60), nullable=False, unique=True),
        sa.Column("descripcion", sa.String(255), nullable=False),
        *_tiempos(),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False, unique=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("descripcion", sa.String(255)),
        *_tiempos(),
    )
    op.create_table(
        "roles_permisos",
        sa.Column("rol_id", sa.Uuid(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permiso_id", sa.Uuid(), sa.ForeignKey("permisos.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("rol_id", sa.Uuid(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("intentos_fallidos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("bloqueado_hasta", sa.DateTime(timezone=True)),
        sa.Column("ultimo_acceso", sa.DateTime(timezone=True)),
        *_tiempos(),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.create_table(
        "sesiones_refresh",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("familia_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocado_en", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("ip", sa.String(45)),
        *_tiempos(),
    )
    op.create_index("ix_sesiones_refresh_usuario_id", "sesiones_refresh", ["usuario_id"])
    op.create_index("ix_sesiones_refresh_familia_id", "sesiones_refresh", ["familia_id"])

    op.create_table(
        "configuracion",
        sa.Column("clave", sa.String(80), primary_key=True),
        sa.Column("valor", postgresql.JSONB(), nullable=False),
        sa.Column("descripcion", sa.String(255)),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
    )

    op.create_table(
        "auditoria",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("accion", sa.String(80), nullable=False),
        sa.Column("entidad", sa.String(60), nullable=False),
        sa.Column("entidad_id", sa.String(64)),
        sa.Column("antes", postgresql.JSONB()),
        sa.Column("despues", postgresql.JSONB()),
        sa.Column("ip", sa.String(45)),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_auditoria_usuario_id", "auditoria", ["usuario_id"])
    op.create_index("ix_auditoria_accion", "auditoria", ["accion"])

    # La bitácora es de solo agregar: ni siquiera la aplicación puede editar o borrar filas.
    op.execute(
        """
        CREATE FUNCTION auditoria_solo_agregar() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'La tabla auditoria es de solo agregar';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER auditoria_inmutable
        BEFORE UPDATE OR DELETE ON auditoria
        FOR EACH ROW EXECUTE FUNCTION auditoria_solo_agregar();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS auditoria_inmutable ON auditoria")
    op.execute("DROP FUNCTION IF EXISTS auditoria_solo_agregar()")
    op.drop_table("auditoria")
    op.drop_table("configuracion")
    op.drop_table("sesiones_refresh")
    op.drop_table("usuarios")
    op.drop_table("roles_permisos")
    op.drop_table("roles")
    op.drop_table("permisos")
