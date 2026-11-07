"""Perfil del club: usuario de TikTok

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("perfil_club", sa.Column("tiktok", sa.String(60)))


def downgrade() -> None:
    op.drop_column("perfil_club", "tiktok")
