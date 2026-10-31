"""Año de fundación del club (el sitio muestra los años que lleva formando deportistas)

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("perfil_club", sa.Column("fundado_en", sa.Integer()))
    op.create_check_constraint("ck_perfil_club_fundado", "perfil_club", "fundado_en BETWEEN 1900 AND 2100")


def downgrade() -> None:
    op.drop_constraint("ck_perfil_club_fundado", "perfil_club", type_="check")
    op.drop_column("perfil_club", "fundado_en")
