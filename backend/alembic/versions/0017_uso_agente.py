"""Asistente de IA: registro de uso por pregunta (límite diario y gasto) y su parámetro

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uso_agente",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tokens_entrada", sa.Integer(), nullable=False),
        sa.Column("tokens_salida", sa.Integer(), nullable=False),
        sa.Column("tokens_cache", sa.Integer(), nullable=False),
        sa.Column("herramientas", postgresql.JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_uso_agente_usuario_id", "uso_agente", ["usuario_id"])
    op.create_index("ix_uso_agente_creado_en", "uso_agente", ["creado_en"])
    op.execute(
        "INSERT INTO configuracion (clave, valor, descripcion) VALUES ('agente_mensajes_por_dia', '40', "
        "'Preguntas al asistente de IA por usuario y día (0 = apagado)') ON CONFLICT (clave) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM configuracion WHERE clave = 'agente_mensajes_por_dia'")
    op.drop_table("uso_agente")
