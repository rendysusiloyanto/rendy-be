"""learning: add video_id and thumbnail_path

Revision ID: 013
Revises: 012
Create Date: 2025-02-24

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("learnings", sa.Column("video_id", sa.String(36), sa.ForeignKey("videos.id"), nullable=True))
    op.add_column("learnings", sa.Column("thumbnail_path", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("learnings", "thumbnail_path")
    op.drop_column("learnings", "video_id")
