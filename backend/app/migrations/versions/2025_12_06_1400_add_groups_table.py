"""add rooms table

Revision ID: 2025_12_06_1400
Revises: 2025_09_25_1200
Create Date: 2025-12-06 14:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2025_12_06_1400"
down_revision: Union[str, None] = "2025_09_25_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # rooms
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("participants", postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=list),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_rooms_creator_id", "rooms", ["creator_id"], unique=False)
    op.create_index("idx_rooms_created_at", "rooms", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_rooms_created_at", table_name="rooms")
    op.drop_index("idx_rooms_creator_id", table_name="rooms")
    op.drop_table("rooms")
