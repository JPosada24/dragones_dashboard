"""Autorización de tratamiento de datos (Ley 1581) e imagen de cada alumno

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Quién autorizó (acudiente o el alumno mayor), cuándo se registró y quién del club lo registró.
    # Los alumnos que ya existen quedan sin autorización: el panel los señala para registrarla.
    op.add_column("alumnos", sa.Column("autoriza_datos_en", sa.DateTime(timezone=True)))
    op.add_column("alumnos", sa.Column("autoriza_datos_nombre", sa.String(120)))
    op.add_column(
        "alumnos",
        sa.Column("autoriza_datos_registro", sa.Uuid(), sa.ForeignKey("usuarios.id", name="fk_alumnos_autoriza_registro")),
    )
    op.add_column("alumnos", sa.Column("autoriza_imagen", sa.Boolean()))
    op.create_check_constraint(
        "ck_alumnos_autorizacion_completa", "alumnos",
        "(autoriza_datos_en IS NULL) = (autoriza_datos_nombre IS NULL)"
        " AND (autoriza_datos_en IS NULL) = (autoriza_imagen IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_alumnos_autorizacion_completa", "alumnos", type_="check")
    op.drop_column("alumnos", "autoriza_imagen")
    op.drop_column("alumnos", "autoriza_datos_registro")
    op.drop_column("alumnos", "autoriza_datos_nombre")
    op.drop_column("alumnos", "autoriza_datos_en")
