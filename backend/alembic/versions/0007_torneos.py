"""Torneos: equipos (clubes externos) inscritos, cupo, lista de espera y pagos

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _tiempos() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "torneos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("rama", sa.String(10), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("fecha_limite_inscripcion", sa.Date(), nullable=False),
        sa.Column("lugar", sa.String(120)),
        sa.Column("cupo_equipos", sa.Integer(), nullable=False),
        sa.Column("valor_inscripcion", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("motivo_cancelacion", sa.String(255)),
        sa.Column("creado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        *_tiempos(),
        sa.CheckConstraint("rama IN ('masculina', 'femenina')", name="ck_torneos_rama"),
        sa.CheckConstraint("estado IN ('programado', 'cancelado')", name="ck_torneos_estado"),
        sa.CheckConstraint("fecha_fin >= fecha_inicio", name="ck_torneos_fechas"),
        sa.CheckConstraint("fecha_limite_inscripcion <= fecha_inicio", name="ck_torneos_limite"),
        sa.CheckConstraint("cupo_equipos BETWEEN 2 AND 200", name="ck_torneos_cupo"),
        sa.CheckConstraint("valor_inscripcion >= 0", name="ck_torneos_valor"),
    )
    op.create_index("ix_torneos_fecha_inicio", "torneos", ["fecha_inicio"])

    op.create_table(
        "equipos_torneo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("torneo_id", sa.Uuid(), sa.ForeignKey("torneos.id"), nullable=False),
        sa.Column("nombre_club", sa.String(120), nullable=False),
        sa.Column("ciudad", sa.String(80), nullable=False),
        sa.Column("delegado_nombre", sa.String(120), nullable=False),
        sa.Column("delegado_telefono", sa.String(20), nullable=False),
        sa.Column("delegado_email", sa.String(254)),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("valor", sa.Integer(), nullable=False),
        sa.Column("monto_pagado", sa.Integer(), nullable=False),
        sa.Column("motivo_retiro", sa.String(255)),
        sa.Column("inscrito_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        *_tiempos(),
        sa.CheckConstraint(
            "estado IN ('pendiente_pago', 'confirmado', 'en_espera', 'retirado')", name="ck_equipos_torneo_estado"
        ),
        sa.CheckConstraint("monto_pagado >= 0", name="ck_equipos_torneo_monto"),
    )
    op.create_index("ix_equipos_torneo_torneo_id", "equipos_torneo", ["torneo_id"])
    op.create_index(
        "ux_equipos_torneo_club", "equipos_torneo", ["torneo_id", sa.text("lower(nombre_club)")], unique=True,
        postgresql_where=sa.text("estado <> 'retirado'"),
    )

    op.create_table(
        "pagos_equipo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("equipo_id", sa.Uuid(), sa.ForeignKey("equipos_torneo.id"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("monto", sa.Integer(), nullable=False),
        sa.Column("anula_id", sa.Uuid(), sa.ForeignKey("pagos_equipo.id"), unique=True),
        sa.Column("motivo", sa.String(500)),
        sa.Column("registrado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(anula_id IS NULL AND monto > 0) OR (anula_id IS NOT NULL AND monto < 0 AND motivo IS NOT NULL)",
            name="ck_pagos_equipo_monto",
        ),
    )
    op.create_index("ix_pagos_equipo_equipo_id", "pagos_equipo", ["equipo_id"])
    op.execute(
        """
        CREATE TRIGGER pagos_equipo_inmutable
        BEFORE UPDATE OR DELETE ON pagos_equipo
        FOR EACH ROW EXECUTE FUNCTION solo_agregar();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS pagos_equipo_inmutable ON pagos_equipo")
    op.drop_table("pagos_equipo")
    op.drop_table("equipos_torneo")
    op.drop_table("torneos")
