"""Torneos realizados: sección del sitio con los torneos ya jugados y su anuncio

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "torneos_realizados",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("lugar", sa.String(120)),
        sa.Column("resumen", sa.String(600)),
        sa.Column("publicado", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("album_id", sa.Uuid(), sa.ForeignKey("albumes.id", ondelete="SET NULL")),
        sa.Column("anuncio_clave", sa.String(32)),
        sa.Column("anuncio_mini_clave", sa.String(32)),
        sa.Column("anuncio_ancho", sa.Integer()),
        sa.Column("anuncio_alto", sa.Integer()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_torneos_realizados_fecha", "torneos_realizados", ["fecha"])


def downgrade() -> None:
    op.drop_index("ix_torneos_realizados_fecha", table_name="torneos_realizados")
    op.drop_table("torneos_realizados")
