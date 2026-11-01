"""Nivel del alumno: iniciación o avanzado (el club enseña por niveles, cada uno con ambas ramas)

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Los alumnos que ya existen quedan en iniciación; el staff corrige a quien esté en avanzado.
    op.add_column(
        "alumnos", sa.Column("nivel", sa.String(10), nullable=False, server_default="iniciacion"),
    )
    op.create_check_constraint("ck_alumnos_nivel", "alumnos", "nivel IN ('iniciacion', 'avanzado')")
    op.create_index("ix_alumnos_nivel", "alumnos", ["nivel"])


def downgrade() -> None:
    op.drop_index("ix_alumnos_nivel", table_name="alumnos")
    op.drop_constraint("ck_alumnos_nivel", "alumnos", type_="check")
    op.drop_column("alumnos", "nivel")
