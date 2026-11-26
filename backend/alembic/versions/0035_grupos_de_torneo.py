"""Sorteo de grupos por rama (con cabezas de serie, sede por grupo y actas); fecha límite de inscripción opcional;
el equipo ya no lleva sede propia

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

LETRAS = "letra IN ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H')"
RAMAS = "rama IN ('masculina', 'femenina')"


def upgrade() -> None:
    # Las sedes de la jornada son para todos los equipos: se informan, no se asignan a cada uno.
    op.drop_column("equipos_torneo", "sede")
    # Sin fecha límite el sitio recibe inscripciones hasta el día de inicio.
    op.alter_column("torneos", "fecha_limite_inscripcion", nullable=True)

    op.create_table(
        "sorteos_grupos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("torneo_id", sa.Uuid(), sa.ForeignKey("torneos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rama", sa.String(10), nullable=False),
        sa.Column("sorteado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sorteado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("confirmado_en", sa.DateTime(timezone=True)),
        sa.Column("confirmado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.CheckConstraint(RAMAS, name="ck_sorteos_grupos_rama"),
        sa.UniqueConstraint("torneo_id", "rama", name="uq_sorteos_grupos_rama"),
    )
    op.create_table(
        "grupos_torneo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sorteo_id", sa.Uuid(), sa.ForeignKey("sorteos_grupos.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("letra", sa.String(1), nullable=False),
        sa.Column("sede", sa.String(120)),
        sa.CheckConstraint(LETRAS, name="ck_grupos_torneo_letra"),
        sa.UniqueConstraint("sorteo_id", "letra", name="uq_grupos_torneo_letra"),
    )
    op.add_column("equipos_torneo", sa.Column(
        "grupo_id", sa.Uuid(), sa.ForeignKey("grupos_torneo.id", ondelete="SET NULL"),
    ))
    op.create_index("ix_equipos_torneo_grupo_id", "equipos_torneo", ["grupo_id"])
    op.add_column("equipos_torneo", sa.Column(
        "cabeza_serie", sa.Boolean(), nullable=False, server_default=sa.text("false"),
    ))

    op.create_table(
        "actas_grupos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("torneo_id", sa.Uuid(), sa.ForeignKey("torneos.id"), nullable=False, index=True),
        sa.Column("rama", sa.String(10), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("grupos", postgresql.JSONB(), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("confirmado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(RAMAS, name="ck_actas_grupos_rama"),
        sa.UniqueConstraint("torneo_id", "rama", "orden", name="uq_actas_grupos_orden"),
    )
    op.execute("""
        CREATE TRIGGER actas_grupos_inmutable BEFORE UPDATE OR DELETE ON actas_grupos
        FOR EACH ROW EXECUTE FUNCTION solo_agregar();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS actas_grupos_inmutable ON actas_grupos")
    op.drop_table("actas_grupos")
    op.drop_column("equipos_torneo", "cabeza_serie")
    op.drop_index("ix_equipos_torneo_grupo_id", table_name="equipos_torneo")
    op.drop_column("equipos_torneo", "grupo_id")
    op.drop_table("grupos_torneo")
    op.drop_table("sorteos_grupos")
    op.execute("UPDATE torneos SET fecha_limite_inscripcion = fecha_inicio WHERE fecha_limite_inscripcion IS NULL")
    op.alter_column("torneos", "fecha_limite_inscripcion", nullable=False)
    op.add_column("equipos_torneo", sa.Column("sede", sa.String(120)))
