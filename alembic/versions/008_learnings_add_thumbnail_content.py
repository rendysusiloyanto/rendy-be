"""learnings: add thumbnail and content

Revision ID: 008
Revises: 007
Create Date: 2025-02-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("learnings", sa.Column("thumbnail", sa.String(512), nullable=True))
    op.add_column("learnings", sa.Column("content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("learnings", "content")
    op.drop_column("learnings", "thumbnail")
