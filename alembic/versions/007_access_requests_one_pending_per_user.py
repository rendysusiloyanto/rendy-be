"""access_requests: hapus duplikat PENDING, satu PENDING per user_id

Revision ID: 007
Revises: 006
Create Date: 2025-02-23

"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Hapus duplikat PENDING: simpan hanya yang requested_at terbaru per user_id
    op.execute("""
        DELETE FROM access_requests a
        USING access_requests b
        WHERE a.user_id = b.user_id
          AND a.status = 'PENDING'
          AND b.status = 'PENDING'
          AND a.requested_at < b.requested_at
    """)
    # Satu PENDING per user (partial unique index)
    op.create_index(
        "ix_access_requests_user_id_pending",
        "access_requests",
        ["user_id"],
        unique=True,
        postgresql_where=text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_access_requests_user_id_pending",
        table_name="access_requests",
    )
