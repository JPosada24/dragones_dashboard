"""Tutorial: recorridos de cada pestaña que ya vio cada cuenta

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("tutoriales_vistos", postgresql.ARRAY(sa.String(60)), nullable=False,
                                        server_default=sa.text("'{}'")))


def downgrade() -> None:
    op.drop_column("usuarios", "tutoriales_vistos")
