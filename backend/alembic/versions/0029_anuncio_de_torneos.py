"""Anuncio (flyer) de los torneos abiertos, y de qué torneo salió cada torneo realizado

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

COLUMNAS = ("anuncio_clave", "anuncio_mini_clave", "anuncio_ancho", "anuncio_alto")


def upgrade() -> None:
    op.add_column("torneos", sa.Column("anuncio_clave", sa.String(32)))
    op.add_column("torneos", sa.Column("anuncio_mini_clave", sa.String(32)))
    op.add_column("torneos", sa.Column("anuncio_ancho", sa.Integer()))
    op.add_column("torneos", sa.Column("anuncio_alto", sa.Integer()))
    # Un torneo se pasa a «realizados» una sola vez (unique); si no salió de uno de la plataforma, queda vacío.
    op.add_column("torneos_realizados", sa.Column(
        "torneo_id", sa.Uuid(), sa.ForeignKey("torneos.id", ondelete="SET NULL"), unique=True))


def downgrade() -> None:
    op.drop_column("torneos_realizados", "torneo_id")
    for columna in reversed(COLUMNAS):
        op.drop_column("torneos", columna)
