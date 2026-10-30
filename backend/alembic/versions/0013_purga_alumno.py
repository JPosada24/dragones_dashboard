"""Purga controlada de alumnos y vencimiento inmediato de tokens al cambiar la contraseña

- El SuperAdmin puede eliminar a un alumno con toda su información.

Las tablas de evidencia (pagos, prórrogas, actas) siguen sin admitir cambios ni borrados, salvo dentro de la
transacción que elimina a un alumno, que activa `SET LOCAL dragones.purga = 'on'` (solo dura esa transacción).
La auditoría nunca se puede borrar.

- `usuarios.credenciales_version`: va dentro del token; al cambiar la contraseña o el rol sube, y los tokens
  emitidos antes dejan de valer de inmediato (incluido el de acceso, que dura 15 minutos).

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("credenciales_version", sa.Integer(), server_default=sa.text("0"),
                                        nullable=False))
    op.execute(
        """
        CREATE OR REPLACE FUNCTION solo_agregar() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND TG_TABLE_NAME <> 'auditoria'
               AND current_setting('dragones.purga', true) = 'on' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'La tabla % es de solo agregar', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.drop_column("usuarios", "credenciales_version")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION solo_agregar() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'La tabla % es de solo agregar', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
