"""Rifas: talonarios, puestos, pagos de puestos y acta de sorteo

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _tiempos() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "rifas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("anio", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("premio", sa.String(255), nullable=False),
        sa.Column("fecha_sorteo", sa.Date(), nullable=False),
        sa.Column("puestos_por_talonario", sa.Integer(), nullable=False),
        sa.Column("precio_puesto", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("motivo_cancelacion", sa.String(255)),
        sa.Column("creado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        *_tiempos(),
        sa.CheckConstraint("estado IN ('abierta', 'sorteada', 'cancelada')", name="ck_rifas_estado"),
        sa.CheckConstraint("numero >= 1", name="ck_rifas_numero"),
        sa.CheckConstraint("puestos_por_talonario BETWEEN 1 AND 100", name="ck_rifas_puestos"),
        sa.CheckConstraint("precio_puesto > 0", name="ck_rifas_precio"),
        sa.UniqueConstraint("anio", "numero", name="uq_rifas_anio_numero"),
    )

    op.create_table(
        "talonarios",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rifa_id", sa.Uuid(), sa.ForeignKey("rifas.id"), nullable=False),
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id"), nullable=False),
        sa.Column("indice", sa.Integer(), nullable=False),
        *_tiempos(),
        sa.UniqueConstraint("rifa_id", "alumno_id", name="uq_talonarios_rifa_alumno"),
        sa.UniqueConstraint("rifa_id", "indice", name="uq_talonarios_rifa_indice"),
    )
    op.create_index("ix_talonarios_rifa_id", "talonarios", ["rifa_id"])
    op.create_index("ix_talonarios_alumno_id", "talonarios", ["alumno_id"])

    op.create_table(
        "puestos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rifa_id", sa.Uuid(), sa.ForeignKey("rifas.id"), nullable=False),
        sa.Column("talonario_id", sa.Uuid(), sa.ForeignKey("talonarios.id"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("comprador_nombre", sa.String(120)),
        sa.Column("comprador_telefono", sa.String(20)),
        sa.Column("monto_pagado", sa.Integer(), nullable=False),
        *_tiempos(),
        sa.UniqueConstraint("rifa_id", "numero", name="uq_puestos_rifa_numero"),
        sa.CheckConstraint("monto_pagado >= 0", name="ck_puestos_monto"),
    )
    op.create_index("ix_puestos_talonario_id", "puestos", ["talonario_id"])

    op.create_table(
        "pagos_puesto",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("puesto_id", sa.Uuid(), sa.ForeignKey("puestos.id"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("monto", sa.Integer(), nullable=False),
        sa.Column("anula_id", sa.Uuid(), sa.ForeignKey("pagos_puesto.id"), unique=True),
        sa.Column("motivo", sa.String(500)),
        sa.Column("registrado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(anula_id IS NULL AND monto > 0) OR (anula_id IS NOT NULL AND monto < 0 AND motivo IS NOT NULL)",
            name="ck_pagos_puesto_monto",
        ),
    )
    op.create_index("ix_pagos_puesto_puesto_id", "pagos_puesto", ["puesto_id"])

    op.create_table(
        "actas_sorteo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rifa_id", sa.Uuid(), sa.ForeignKey("rifas.id"), nullable=False, unique=True),
        sa.Column("numero_ganador", sa.Integer(), nullable=False),
        sa.Column("puesto_id", sa.Uuid(), sa.ForeignKey("puestos.id"), nullable=False),
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id"), nullable=False),
        sa.Column("comprador_nombre", sa.String(120)),
        sa.Column("participantes", postgresql.JSONB(), nullable=False),
        sa.Column("total_participantes", sa.Integer(), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("jugado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("jugado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Dinero recibido y resultado del sorteo: evidencia que no se edita ni se borra (función creada en la 0002).
    for tabla in ("pagos_puesto", "actas_sorteo"):
        op.execute(
            f"""
            CREATE TRIGGER {tabla}_inmutable
            BEFORE UPDATE OR DELETE ON {tabla}
            FOR EACH ROW EXECUTE FUNCTION solo_agregar();
            """
        )


def downgrade() -> None:
    for tabla in ("actas_sorteo", "pagos_puesto"):
        op.execute(f"DROP TRIGGER IF EXISTS {tabla}_inmutable ON {tabla}")
    op.drop_table("actas_sorteo")
    op.drop_table("pagos_puesto")
    op.drop_table("puestos")
    op.drop_table("talonarios")
    op.drop_table("rifas")
