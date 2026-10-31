"""Aviso de inasistencia: el motivo de la justificación es opcional

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("justificaciones", "motivo", existing_type=sa.String(500), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE justificaciones SET motivo = 'Sin motivo' WHERE motivo IS NULL")
    op.alter_column("justificaciones", "motivo", existing_type=sa.String(500), nullable=False)
