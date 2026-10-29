"""Causa de la expulsión (mora o manual) en la inscripción

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inscripciones", sa.Column("causa_expulsion", sa.String(10)))
    # Lo marcado antes de esta versión fue a mano: no lo debe revertir el proceso de mora.
    op.execute("UPDATE inscripciones SET causa_expulsion = 'manual' WHERE estado IN ('a_expulsar', 'expulsado')")
    op.create_check_constraint(
        "ck_inscripciones_causa_expulsion", "inscripciones",
        "causa_expulsion IS NULL OR causa_expulsion IN ('mora', 'manual')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_inscripciones_causa_expulsion", "inscripciones", type_="check")
    op.drop_column("inscripciones", "causa_expulsion")
