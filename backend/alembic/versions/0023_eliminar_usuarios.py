"""Usuarios eliminados (solo el SuperAdmin)

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La fila se conserva porque pagos, asistencias y la auditoría apuntan a quien los registró; se libera el
    # correo, se bloquea el acceso y deja de aparecer. El permiso usuarios.eliminar lo siembra el catálogo.
    op.add_column("usuarios", sa.Column("eliminado_en", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("usuarios", "eliminado_en")
