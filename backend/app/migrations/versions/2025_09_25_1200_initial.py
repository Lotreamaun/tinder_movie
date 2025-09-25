"""initial schema

Revision ID: 2025_09_25_1200
Revises: 
Create Date: 2025-09-25 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2025_09_25_1200"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUM type for swipe_type
    swipe_type = postgresql.ENUM("like", "dislike", name="swipe_type")
    swipe_type.create(op.get_bind(), checkfirst=True)

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_active", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_users_active", "users", ["last_active"], unique=False)

    # movies
    op.create_table(
        "movies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("kinopoisk_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("title_original", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("genre", sa.String(), nullable=False),
        sa.Column("poster_url", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("idx_movies_kinopoisk_id", "movies", ["kinopoisk_id"], unique=False)

    # user_swipes
    op.create_table(
        "user_swipes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("swipe_type", sa.Enum(name="swipe_type", native_enum=False), nullable=False),
        sa.Column("swiped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("group_participants", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("user_id", "movie_id", "group_participants", name="uq_swipe_user_movie_group"),
    )
    op.create_index("idx_user_swipes_user_id", "user_swipes", ["user_id"], unique=False)

    # matches
    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_notified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("group_participants", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("movie_id", "group_participants", name="uq_match_movie_group"),
    )
    op.create_index(
        "idx_matches_group_participants",
        "matches",
        ["group_participants"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("idx_matches_group_participants", table_name="matches")
    op.drop_table("matches")

    op.drop_index("idx_user_swipes_user_id", table_name="user_swipes")
    op.drop_table("user_swipes")

    op.drop_index("idx_movies_kinopoisk_id", table_name="movies")
    op.drop_table("movies")

    op.drop_index("idx_users_active", table_name="users")
    op.drop_table("users")

    # drop ENUM
    postgresql.ENUM(name="swipe_type").drop(op.get_bind(), checkfirst=True)


