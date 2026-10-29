"""Sesiones de entrenamiento, asistencia, justificaciones y multas

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _tiempos() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "sesiones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rama", sa.String(10), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("lugar", sa.String(120)),
        sa.Column("cancelada", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("motivo_cancelacion", sa.String(255)),
        sa.Column("cerrada_en", sa.DateTime(timezone=True)),
        sa.Column("creado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        *_tiempos(),
        sa.CheckConstraint("rama IN ('masculina', 'femenina')", name="ck_sesiones_rama"),
        sa.CheckConstraint("hora_fin > hora_inicio", name="ck_sesiones_horario"),
        sa.UniqueConstraint("rama", "fecha", "hora_inicio", name="uq_sesiones_rama_fecha_hora"),
    )
    op.create_index("ix_sesiones_fecha", "sesiones", ["fecha"])

    op.create_table(
        "asistencias",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sesion_id", sa.Uuid(), sa.ForeignKey("sesiones.id"), nullable=False),
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id"), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("origen", sa.String(15), nullable=False),
        sa.Column("marcado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        *_tiempos(),
        sa.CheckConstraint("estado IN ('presente', 'ausente', 'justificado')", name="ck_asistencias_estado"),
        sa.CheckConstraint(
            "origen IN ('propia', 'grupo', 'cierre', 'correccion', 'justificacion')", name="ck_asistencias_origen"
        ),
        sa.UniqueConstraint("sesion_id", "alumno_id", name="uq_asistencias_sesion_alumno"),
    )
    op.create_index("ix_asistencias_alumno_id", "asistencias", ["alumno_id"])

    op.create_table(
        "justificaciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sesion_id", sa.Uuid(), sa.ForeignKey("sesiones.id"), nullable=False),
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id"), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("creada_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("revisada_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("revisada_en", sa.DateTime(timezone=True)),
        sa.Column("comentario", sa.String(255)),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("estado IN ('pendiente', 'aprobada', 'rechazada')", name="ck_justificaciones_estado"),
    )
    op.create_index("ix_justificaciones_sesion_id", "justificaciones", ["sesion_id"])
    op.create_index("ix_justificaciones_alumno_id", "justificaciones", ["alumno_id"])
    op.create_index(
        "ux_justificaciones_viva", "justificaciones", ["sesion_id", "alumno_id"], unique=True,
        postgresql_where=sa.text("estado IN ('pendiente', 'aprobada')"),
    )

    op.create_table(
        "multas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id"), nullable=False),
        sa.Column("sesion_id", sa.Uuid(), sa.ForeignKey("sesiones.id"), nullable=False),
        sa.Column("valor", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("fecha_pago", sa.Date()),
        sa.Column("pago_registrado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("motivo_anulacion", sa.String(255)),
        sa.Column("anulada_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        *_tiempos(),
        sa.CheckConstraint("estado IN ('pendiente', 'pagada', 'anulada')", name="ck_multas_estado"),
        sa.CheckConstraint("valor > 0", name="ck_multas_valor"),
    )
    op.create_index("ix_multas_alumno_id", "multas", ["alumno_id"])
    op.create_index("ix_multas_estado", "multas", ["estado"])
    op.create_index(
        "ux_multas_vigente", "multas", ["alumno_id", "sesion_id"], unique=True,
        postgresql_where=sa.text("estado IN ('pendiente', 'pagada')"),
    )


def downgrade() -> None:
    op.drop_table("multas")
    op.drop_table("justificaciones")
    op.drop_table("asistencias")
    op.drop_table("sesiones")
