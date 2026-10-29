"""Anulación de abonos: movimiento negativo que revierte un abono, con motivo

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pagos_inscripcion", sa.Column("anula_id", sa.Uuid(), sa.ForeignKey("pagos_inscripcion.id"), unique=True)
    )
    op.add_column("pagos_inscripcion", sa.Column("motivo", sa.String(500)))
    op.drop_constraint("ck_pagos_inscripcion_monto", "pagos_inscripcion", type_="check")
    op.create_check_constraint(
        "ck_pagos_inscripcion_monto",
        "pagos_inscripcion",
        "(anula_id IS NULL AND monto > 0) OR (anula_id IS NOT NULL AND monto < 0 AND motivo IS NOT NULL)",
    )


def downgrade() -> None:
    # Las anulaciones no caben en el esquema anterior: se descartan al bajar. El trigger append-only
    # bloquearía el DELETE, así que se desactiva solo durante esta limpieza.
    op.execute("ALTER TABLE pagos_inscripcion DISABLE TRIGGER pagos_inscripcion_inmutable")
    op.execute("DELETE FROM pagos_inscripcion WHERE anula_id IS NOT NULL")
    op.execute("ALTER TABLE pagos_inscripcion ENABLE TRIGGER pagos_inscripcion_inmutable")
    op.drop_constraint("ck_pagos_inscripcion_monto", "pagos_inscripcion", type_="check")
    op.create_check_constraint("ck_pagos_inscripcion_monto", "pagos_inscripcion", "monto > 0")
    op.drop_column("pagos_inscripcion", "motivo")
    op.drop_column("pagos_inscripcion", "anula_id")
