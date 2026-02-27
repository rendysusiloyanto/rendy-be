"""learnings: add variant (introduction | full)

Revision ID: 014
Revises: 013
Create Date: 2026-02-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learnings",
        sa.Column("variant", sa.String(32), nullable=False, server_default="introduction"),
    )


def downgrade() -> None:
    op.drop_column("learnings", "variant")
