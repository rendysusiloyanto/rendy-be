"""create ukk_test_results table (leaderboard)

Revision ID: 003
Revises: 002
Create Date: 2025-02-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ukk_test_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("grade", sa.String(5), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ukk_test_results_user_id", "ukk_test_results", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ukk_test_results_user_id", table_name="ukk_test_results")
    op.drop_table("ukk_test_results")
