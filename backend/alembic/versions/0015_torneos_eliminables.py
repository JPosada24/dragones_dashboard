"""Torneos eliminables: estado «eliminado» (desaparece de las vistas; sus pagos se conservan)

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-30
"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_torneos_estado", "torneos", type_="check")
    op.create_check_constraint("ck_torneos_estado", "torneos", "estado IN ('programado', 'cancelado', 'eliminado')")


def downgrade() -> None:
    op.execute("UPDATE torneos SET estado = 'cancelado' WHERE estado = 'eliminado'")
    op.drop_constraint("ck_torneos_estado", "torneos", type_="check")
    op.create_check_constraint("ck_torneos_estado", "torneos", "estado IN ('programado', 'cancelado')")
