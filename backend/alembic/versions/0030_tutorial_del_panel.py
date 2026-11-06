"""Tutorial guiado del panel: cuándo lo vio (o saltó) cada cuenta

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("tutorial_visto_en", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("usuarios", "tutorial_visto_en")
