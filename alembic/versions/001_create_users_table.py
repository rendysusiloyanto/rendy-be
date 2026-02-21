"""create users table

Revision ID: 001
Revises:
Create Date: 2025-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("class_name", sa.String(50), nullable=True),
        sa.Column("attendance_number", sa.String(5), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="GUEST"),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("users")
