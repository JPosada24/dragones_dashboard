"""Abonos (pagos parciales) de inscripciones

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pagos_inscripcion",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("inscripcion_id", sa.Uuid(), sa.ForeignKey("inscripciones.id"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("monto", sa.Integer(), nullable=False),
        sa.Column("registrado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("monto > 0", name="ck_pagos_inscripcion_monto"),
    )
    op.create_index("ix_pagos_inscripcion_inscripcion_id", "pagos_inscripcion", ["inscripcion_id"])

    # Los pagos únicos registrados antes de esta versión pasan a ser un abono.
    op.execute(
        """
        INSERT INTO pagos_inscripcion (id, inscripcion_id, fecha, monto, creado_en)
        SELECT gen_random_uuid(), id, fecha_pago, monto_pagado, actualizado_en
        FROM inscripciones
        WHERE fecha_pago IS NOT NULL AND monto_pagado > 0
        """
    )

    # Los abonos son evidencia de dinero recibido: no se editan ni se borran (función creada en la 0002).
    op.execute(
        """
        CREATE TRIGGER pagos_inscripcion_inmutable
        BEFORE UPDATE OR DELETE ON pagos_inscripcion
        FOR EACH ROW EXECUTE FUNCTION solo_agregar();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS pagos_inscripcion_inmutable ON pagos_inscripcion")
    op.drop_table("pagos_inscripcion")
