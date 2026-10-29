"""Notificaciones: bandeja, correo (con reintentos) y WhatsApp manual

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notificaciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clave", sa.String(200), nullable=False, unique=True),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("titulo", sa.String(150), nullable=False),
        sa.Column("mensaje", sa.String(1000), nullable=False),
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id")),
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("leida_en", sa.DateTime(timezone=True)),
        sa.Column("email_destino", sa.String(254)),
        sa.Column("email_estado", sa.String(12), nullable=False),
        sa.Column("email_intentos", sa.Integer(), nullable=False),
        sa.Column("email_error", sa.String(255)),
        sa.Column("email_proximo_intento", sa.DateTime(timezone=True)),
        sa.Column("email_enviado_en", sa.DateTime(timezone=True)),
        sa.Column("telefono_destino", sa.String(20)),
        sa.Column("whatsapp_estado", sa.String(12), nullable=False),
        sa.Column("whatsapp_marcado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("whatsapp_marcado_en", sa.DateTime(timezone=True)),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("email_estado IN ('no_aplica', 'pendiente', 'enviado', 'fallido')", name="ck_notif_email"),
        sa.CheckConstraint(
            "whatsapp_estado IN ('no_aplica', 'pendiente', 'enviado', 'descartado')", name="ck_notif_whatsapp"
        ),
    )
    for columna in ("tipo", "alumno_id", "usuario_id", "email_estado", "whatsapp_estado"):
        op.create_index(f"ix_notificaciones_{columna}", "notificaciones", [columna])


def downgrade() -> None:
    op.drop_table("notificaciones")
