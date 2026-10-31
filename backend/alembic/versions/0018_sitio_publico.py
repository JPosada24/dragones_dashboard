"""Sitio público del club: perfil, álbumes y fotos, videos, equipo de trabajo; origen de la inscripción a torneos

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def _tiempos() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "perfil_club",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("lema", sa.String(160)),
        sa.Column("ciudad", sa.String(80)),
        sa.Column("sede", sa.String(160)),
        sa.Column("mision", sa.Text()),
        sa.Column("vision", sa.Text()),
        sa.Column("historia", sa.Text()),
        sa.Column("whatsapp", sa.String(20)),
        sa.Column("correo", sa.String(254)),
        sa.Column("instagram", sa.String(60)),
        sa.Column("facebook", sa.String(100)),
        sa.Column("publicado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.CheckConstraint("id = 1", name="ck_perfil_club_unico"),
    )
    op.execute("INSERT INTO perfil_club (id, nombre) VALUES (1, 'Club Deportivo Dragones')")
    op.execute(
        "INSERT INTO configuracion (clave, valor, descripcion) VALUES ('foto_max_mb', '12', "
        "'Tamaño máximo de cada foto que se sube a la galería del sitio (MB)') ON CONFLICT (clave) DO NOTHING"
    )
    op.create_table(
        "albumes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("fecha", sa.Date()),
        sa.Column("publicado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_tiempos(),
    )
    op.create_table(
        "fotos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("album_id", sa.Uuid(), sa.ForeignKey("albumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clave", sa.String(32), nullable=False),
        sa.Column("clave_miniatura", sa.String(32), nullable=False),
        sa.Column("ancho", sa.Integer(), nullable=False),
        sa.Column("alto", sa.Integer(), nullable=False),
        sa.Column("autorizada_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        *_tiempos(),
    )
    op.create_index("ix_fotos_album_id", "fotos", ["album_id"])
    op.create_table(
        "videos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("titulo", sa.String(120), nullable=False),
        sa.Column("youtube_id", sa.String(11), nullable=False),
        sa.Column("publicado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_tiempos(),
    )
    op.create_table(
        "integrantes_equipo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("cargo", sa.String(120), nullable=False),
        sa.Column("bio", sa.String(400)),
        sa.Column("orden", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("publicado", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_tiempos(),
    )
    op.add_column("equipos_torneo", sa.Column("origen", sa.String(10), server_default=sa.text("'staff'"),
                                              nullable=False))
    op.add_column("equipos_torneo", sa.Column("autoriza_datos_en", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_equipos_torneo_origen", "equipos_torneo", "origen IN ('staff', 'sitio')")


def downgrade() -> None:
    op.execute("DELETE FROM configuracion WHERE clave = 'foto_max_mb'")
    op.drop_constraint("ck_equipos_torneo_origen", "equipos_torneo", type_="check")
    op.drop_column("equipos_torneo", "autoriza_datos_en")
    op.drop_column("equipos_torneo", "origen")
    for tabla in ("integrantes_equipo", "videos", "fotos", "albumes", "perfil_club"):
        op.drop_table(tabla)
