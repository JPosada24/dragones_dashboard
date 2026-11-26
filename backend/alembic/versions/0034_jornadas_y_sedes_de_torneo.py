"""Torneos por jornadas: cada una con su rama, fecha y sedes; el equipo elige rama y el organizador le asigna sede

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jornadas_torneo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("torneo_id", sa.Uuid(), sa.ForeignKey("torneos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rama", sa.String(10), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("sedes", postgresql.ARRAY(sa.String(120)), nullable=False, server_default=sa.text("'{}'")),
        sa.CheckConstraint("rama IN ('masculina', 'femenina')", name="ck_jornadas_torneo_rama"),
        sa.UniqueConstraint("torneo_id", "rama", "fecha", name="uq_jornadas_torneo_dia"),
    )
    # Cada torneo que ya existe queda con una jornada: su rama, el día de inicio y sin sedes (su lugar sigue igual).
    op.execute(
        "INSERT INTO jornadas_torneo (id, torneo_id, rama, fecha) "
        "SELECT gen_random_uuid(), id, rama, fecha_inicio FROM torneos"
    )
    # Con varias jornadas el torneo puede tener las dos ramas: la rama del torneo queda vacía en ese caso.
    op.alter_column("torneos", "rama", nullable=True)

    op.add_column("equipos_torneo", sa.Column("rama", sa.String(10)))
    op.execute("UPDATE equipos_torneo e SET rama = t.rama FROM torneos t WHERE t.id = e.torneo_id")
    op.alter_column("equipos_torneo", "rama", nullable=False)
    op.create_check_constraint("ck_equipos_torneo_rama", "equipos_torneo", "rama IN ('masculina', 'femenina')")
    op.add_column("equipos_torneo", sa.Column("sede", sa.String(120)))  # la asigna el organizador
    # Un club puede inscribir un equipo por rama (no dos en la misma).
    op.drop_index("ux_equipos_torneo_club", table_name="equipos_torneo")
    op.create_index(
        "ux_equipos_torneo_club", "equipos_torneo", ["torneo_id", "rama", sa.text("lower(nombre_club)")], unique=True,
        postgresql_where=sa.text("estado <> 'retirado'"),
    )


def downgrade() -> None:
    op.drop_index("ux_equipos_torneo_club", table_name="equipos_torneo")
    op.create_index(
        "ux_equipos_torneo_club", "equipos_torneo", ["torneo_id", sa.text("lower(nombre_club)")], unique=True,
        postgresql_where=sa.text("estado <> 'retirado'"),
    )
    op.drop_column("equipos_torneo", "sede")
    op.drop_constraint("ck_equipos_torneo_rama", "equipos_torneo", type_="check")
    op.drop_column("equipos_torneo", "rama")
    op.execute(
        "UPDATE torneos t SET rama = (SELECT j.rama FROM jornadas_torneo j WHERE j.torneo_id = t.id "
        "ORDER BY j.fecha LIMIT 1) WHERE t.rama IS NULL"
    )
    op.alter_column("torneos", "rama", nullable=False)
    op.drop_table("jornadas_torneo")
