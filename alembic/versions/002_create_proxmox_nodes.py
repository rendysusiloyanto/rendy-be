"""create proxmox_nodes table

Revision ID: 002
Revises: 001
Create Date: 2025-02-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proxmox_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("user", sa.String(100), nullable=False, server_default="root"),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("proxmox_nodes")
