"""Permisos ajustados por persona: el SuperAdmin da o quita permisos a un Admin o Entrenador además de su rol

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios_permisos",
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permiso_id", sa.Uuid(), sa.ForeignKey("permisos.id", ondelete="CASCADE"), primary_key=True),
        # true = se le da además de su rol; false = se le quita aunque su rol lo traiga.
        sa.Column("concedido", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("usuarios_permisos")
