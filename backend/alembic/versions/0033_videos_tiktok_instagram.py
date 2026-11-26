"""Videos del sitio: también de TikTok e Instagram (no solo YouTube)

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("plataforma", sa.String(10), nullable=False, server_default="youtube"))
    op.add_column("videos", sa.Column("ruta", sa.String(80)))
    op.execute("UPDATE videos SET ruta = youtube_id")
    op.alter_column("videos", "ruta", nullable=False)
    op.drop_column("videos", "youtube_id")
    op.create_check_constraint("ck_videos_plataforma", "videos", "plataforma IN ('youtube', 'tiktok', 'instagram')")


def downgrade() -> None:
    op.execute("DELETE FROM videos WHERE plataforma <> 'youtube'")
    op.add_column("videos", sa.Column("youtube_id", sa.String(11)))
    op.execute("UPDATE videos SET youtube_id = ruta")
    op.alter_column("videos", "youtube_id", nullable=False)
    op.drop_constraint("ck_videos_plataforma", "videos", type_="check")
    op.drop_column("videos", "ruta")
    op.drop_column("videos", "plataforma")
