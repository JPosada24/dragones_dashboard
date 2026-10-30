"""Entrenador general: los usuarios ya no tienen rama y ver el documento completo es un permiso aparte

El Entrenador ve y gestiona a los alumnos de ambas ramas (permiso "alumnos.ver_todos"). Ver el número de documento
completo, que antes iba con "alumnos.ver_todos", pasa a "alumnos.ver_documento" (Admin y SuperAdmin). Los permisos y
roles se vuelven a sembrar al arrancar (services/catalogos.py); aquí solo se quita lo que ya no existe.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM roles_permisos
        WHERE permiso_id IN (SELECT id FROM permisos WHERE codigo = 'alumnos.ver_rama')
    """)
    op.execute("DELETE FROM permisos WHERE codigo = 'alumnos.ver_rama'")
    op.drop_constraint("ck_usuarios_rama", "usuarios", type_="check")
    op.drop_column("usuarios", "rama")


def downgrade() -> None:
    op.add_column("usuarios", sa.Column("rama", sa.String(10)))
    op.create_check_constraint(
        "ck_usuarios_rama", "usuarios", "rama IS NULL OR rama IN ('masculina', 'femenina')"
    )
