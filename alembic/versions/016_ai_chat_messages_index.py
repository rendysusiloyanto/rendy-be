"""add index (user_id, created_at DESC) on ai_chat_messages for efficient history load

Revision ID: 016
Revises: 015
Create Date: 2026-02-27

"""
from typing import Sequence, Union
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index for efficient "last N messages per user" (Cache-Aside load from DB)
    # PostgreSQL: descending created_at; SQLite ignores postgresql_ops
    op.create_index(
        "ix_ai_chat_messages_user_id_created_at",
        "ai_chat_messages",
        ["user_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_ai_chat_messages_user_id_created_at", table_name="ai_chat_messages")
