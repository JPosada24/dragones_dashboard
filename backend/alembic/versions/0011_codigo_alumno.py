"""Código del alumno por rama (F001, M001…) y copia en cada talonario para el sorteo

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alumnos", sa.Column("codigo", sa.String(8), nullable=True))
    # Los alumnos que ya existen reciben su código en orden de creación, por rama.
    op.execute("""
        UPDATE alumnos a SET codigo = n.codigo
        FROM (
            SELECT id,
                   CASE rama WHEN 'femenina' THEN 'F' ELSE 'M' END
                   || lpad(row_number() OVER (PARTITION BY rama ORDER BY creado_en, id)::text, 3, '0') AS codigo
            FROM alumnos
        ) n
        WHERE a.id = n.id
    """)
    op.alter_column("alumnos", "codigo", nullable=False)
    op.create_unique_constraint("uq_alumnos_codigo", "alumnos", ["codigo"])
    op.create_check_constraint("ck_alumnos_codigo", "alumnos", "codigo ~ '^[FM][0-9]{3,5}$'")

    # Cada talonario guarda el código con el que se entregó: si luego se corrige la rama del alumno,
    # las boletas ya vendidas y el acta del sorteo siguen diciendo lo mismo.
    op.add_column("talonarios", sa.Column("codigo", sa.String(8), nullable=True))
    op.execute("UPDATE talonarios t SET codigo = a.codigo FROM alumnos a WHERE a.id = t.alumno_id")
    op.alter_column("talonarios", "codigo", nullable=False)


def downgrade() -> None:
    op.drop_column("talonarios", "codigo")
    op.drop_constraint("ck_alumnos_codigo", "alumnos", type_="check")
    op.drop_constraint("uq_alumnos_codigo", "alumnos", type_="unique")
    op.drop_column("alumnos", "codigo")
