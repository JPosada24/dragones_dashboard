"""Limitador de intentos compartido (en Postgres) y latido del worker

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Antes vivía en la memoria de cada proceso: con varios procesos de la API cada uno contaba por su lado.
    # `clave` es el SHA-256 de la IP (no se guarda la IP en claro). El worker borra lo de más de un día.
    op.create_table(
        "intentos",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("ambito", sa.String(16), nullable=False),
        sa.Column("clave", sa.String(64), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_intentos_ambito_clave_creado", "intentos", ["ambito", "clave", "creado_en"])
    # Último ciclo del worker: /salud/worker avisa si dejó de correr (para el monitor de disponibilidad).
    op.create_table(
        "latidos",
        sa.Column("servicio", sa.String(30), primary_key=True),
        sa.Column("en", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("latidos")
    op.drop_index("ix_intentos_ambito_clave_creado", table_name="intentos")
    op.drop_table("intentos")
