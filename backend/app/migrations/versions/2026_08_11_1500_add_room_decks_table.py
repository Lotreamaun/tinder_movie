"""add room_decks table

Revision ID: 2026_08_11_1500
Revises: 2025_12_06_1400
Create Date: 2026-08-11 15:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2026_08_11_1500"
down_revision: Union[str, None] = "2025_12_06_1400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # room_decks — общий упорядоченный колод фильмов комнаты
    op.create_table(
        "room_decks",
        sa.Column(
            "room_code",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "movie_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("room_decks")
