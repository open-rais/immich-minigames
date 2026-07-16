"""baseline - users/games/rounds as they existed before Alembic

Recreates the three `minigames` tables exactly as persistence/games.py and persistence/users.py
defined them before this migration was introduced. Every op.create_table is guarded by
`has_table(...)` and skipped if the table is already there - this is what lets a single
`alembic upgrade head` work whether it's hitting a brand new database (nothing exists yet, so this
migration creates everything) or an existing deployment that was previously managed by
Base.metadata.create_all() (tables already exist, so this migration is a no-op here but still gets
recorded as applied, letting later migrations proceed).

Revision ID: 0001
Revises:
Create Date: 2026-07-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name, schema=_SCHEMA)


def upgrade() -> None:
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("username", sa.String(), nullable=False),
            sa.Column("full_name", sa.String(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("email"),
            sa.UniqueConstraint("username"),
            schema=_SCHEMA,
        )

    if not _has_table("games"):
        op.create_table(
            "games",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("owner", sa.String(), nullable=False),
            sa.Column("game_type", sa.String(), nullable=False),
            sa.Column("mode", sa.String(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("finished", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            schema=_SCHEMA,
        )

    if not _has_table("rounds"):
        op.create_table(
            "rounds",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "game_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{_SCHEMA}.games.id"),
                nullable=False,
            ),
            sa.Column("round_index", sa.Integer(), nullable=False),
            sa.Column("score_delta", sa.Integer(), nullable=True),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("game_id", "round_index"),
            schema=_SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("rounds", schema=_SCHEMA)
    op.drop_table("games", schema=_SCHEMA)
    op.drop_table("users", schema=_SCHEMA)
