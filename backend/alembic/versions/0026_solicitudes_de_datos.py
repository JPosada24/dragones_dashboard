"""Registro de solicitudes de habeas data (consultas y reclamos de la Ley 1581) con su plazo legal

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solicitudes_datos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("titular", sa.String(120), nullable=False),
        sa.Column("contacto", sa.String(120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("recibida_el", sa.Date(), nullable=False),
        sa.Column("vence_el", sa.Date(), nullable=False),
        sa.Column("prorrogada", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("motivo_prorroga", sa.String(500)),
        sa.Column("estado", sa.String(12), nullable=False, server_default="en_tramite"),
        sa.Column("respuesta", sa.Text()),
        sa.Column("respondida_en", sa.DateTime(timezone=True)),
        sa.Column("registrada_por", sa.Uuid(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tipo IN ('consulta', 'reclamo')", name="ck_solicitudes_datos_tipo"),
        sa.CheckConstraint("estado IN ('en_tramite', 'respondida')", name="ck_solicitudes_datos_estado"),
        sa.CheckConstraint("(estado = 'respondida') = (respuesta IS NOT NULL)", name="ck_solicitudes_datos_respuesta"),
    )
    op.create_index("ix_solicitudes_datos_estado", "solicitudes_datos", ["estado", "vence_el"])


def downgrade() -> None:
    op.drop_index("ix_solicitudes_datos_estado", table_name="solicitudes_datos")
    op.drop_table("solicitudes_datos")
