"""Entrenamiento general (sin rama) y horario semanal con programación automática

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-29
"""
from datetime import time
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

# Horario inicial del club: lunes, miércoles y sábado (se cambia desde la pantalla de Asistencia).
HORARIO_INICIAL = [(0, time(18), time(20)), (2, time(18), time(20)), (5, time(16), time(18))]


def upgrade() -> None:
    # Las sesiones por rama pasan a ser generales. Si hubiera dos de la misma fecha y hora (una por rama),
    # la restricción nueva fallaría: se detecta antes con un mensaje claro.
    duplicadas = op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM (SELECT 1 FROM sesiones GROUP BY fecha, hora_inicio HAVING count(*) > 1) d"
    ))
    if duplicadas:
        raise RuntimeError("Hay sesiones de ambas ramas con la misma fecha y hora: unifícalas antes de migrar.")
    op.drop_constraint("uq_sesiones_rama_fecha_hora", "sesiones", type_="unique")
    op.drop_constraint("ck_sesiones_rama", "sesiones", type_="check")
    op.drop_column("sesiones", "rama")
    op.create_unique_constraint("uq_sesiones_fecha_hora", "sesiones", ["fecha", "hora_inicio"])
    op.add_column("sesiones", sa.Column("automatica", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("sesiones", sa.Column("causa_cancelacion", sa.String(10)))
    op.execute("UPDATE sesiones SET causa_cancelacion = 'manual' WHERE cancelada")
    op.create_check_constraint(
        "ck_sesiones_causa_cancelacion", "sesiones",
        "causa_cancelacion IS NULL OR causa_cancelacion IN ('festivo', 'torneo', 'horario', 'manual')",
    )

    horario = op.create_table(
        "horario_entrenamiento",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dia_semana", sa.Integer(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("lugar", sa.String(120)),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("dia_semana BETWEEN 0 AND 6", name="ck_horario_dia"),
        sa.CheckConstraint("hora_fin > hora_inicio", name="ck_horario_horas"),
        sa.UniqueConstraint("dia_semana", name="uq_horario_dia"),
    )
    op.bulk_insert(horario, [
        {"id": uuid.uuid4(), "dia_semana": d, "hora_inicio": i, "hora_fin": f, "lugar": None}
        for d, i, f in HORARIO_INICIAL
    ])


def downgrade() -> None:
    op.drop_table("horario_entrenamiento")
    op.drop_constraint("ck_sesiones_causa_cancelacion", "sesiones", type_="check")
    op.drop_column("sesiones", "causa_cancelacion")
    op.drop_column("sesiones", "automatica")
    op.drop_constraint("uq_sesiones_fecha_hora", "sesiones", type_="unique")
    # Sin la rama original, las sesiones vuelven como femeninas (solo para poder revertir en desarrollo).
    op.add_column("sesiones", sa.Column("rama", sa.String(10), server_default="femenina", nullable=False))
    op.alter_column("sesiones", "rama", server_default=None)
    op.create_check_constraint("ck_sesiones_rama", "sesiones", "rama IN ('masculina', 'femenina')")
    op.create_unique_constraint("uq_sesiones_rama_fecha_hora", "sesiones", ["rama", "fecha", "hora_inicio"])
