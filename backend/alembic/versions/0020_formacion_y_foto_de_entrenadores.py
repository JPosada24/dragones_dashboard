"""Sección «La formación va por rotaciones» (6 etapas editables) y foto de los entrenadores

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("perfil_club", sa.Column("formacion_intro", sa.Text()))
    op.add_column("perfil_club", sa.Column("formacion", postgresql.JSONB()))
    op.add_column("integrantes_equipo", sa.Column("foto_clave", sa.String(32)))


def downgrade() -> None:
    op.drop_column("integrantes_equipo", "foto_clave")
    op.drop_column("perfil_club", "formacion")
    op.drop_column("perfil_club", "formacion_intro")
