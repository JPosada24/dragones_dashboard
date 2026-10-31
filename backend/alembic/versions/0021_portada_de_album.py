"""Portada propia de cada álbum (no cuenta como foto del álbum)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("albumes", sa.Column("portada_clave", sa.String(32)))


def downgrade() -> None:
    op.drop_column("albumes", "portada_clave")
