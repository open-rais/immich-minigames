"""drop games.owner, require games.user_id (roadmap #H, F4)

Login is mandatory as of F3 (AuthMiddleware default-denies unauthenticated requests), so the old
anonymous-identity column (`games.owner`, the `X-Owner-Id` header's counterpart) has nothing left
writing to it. This drops it and makes `user_id` `NOT NULL`, collapsing `GamesService`'s owner/
user_id dual branching down to a single `user_id`-only path.

Pre-cutover anonymous games (`user_id IS NULL`) can't survive the `NOT NULL` constraint - decision
[I] in docs/TODO/NEW-AUTH.md: these are deleted (with their rounds, by explicit delete rather than
relying on the ORM-level `cascade="all, delete-orphan"`, which is a session concept, not a DB
constraint) rather than building a one-time "claim by X-Owner-Id" endpoint just to migrate what is,
in this app's current installations, dev/test data.

The two daily-uniqueness indexes (`uq_games_daily_user`, keyed on `user_id`; `uq_games_daily_owner`,
keyed on `owner`, for the anonymous case) collapse into one now that `user_id` is never null.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-29

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.execute(
        f"DELETE FROM {_SCHEMA}.rounds WHERE game_id IN "
        f"(SELECT id FROM {_SCHEMA}.games WHERE user_id IS NULL)"
    )
    op.execute(f"DELETE FROM {_SCHEMA}.games WHERE user_id IS NULL")

    op.alter_column("games", "user_id", nullable=False, schema=_SCHEMA)

    op.drop_index("uq_games_daily_user", table_name="games", schema=_SCHEMA)
    op.drop_index("uq_games_daily_owner", table_name="games", schema=_SCHEMA)
    op.create_index(
        "uq_games_daily",
        "games",
        ["daily_challenge_id", "user_id"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("daily_challenge_id IS NOT NULL"),
    )

    op.drop_index("ix_games_owner_type_mode", table_name="games", schema=_SCHEMA)
    op.drop_column("games", "owner", schema=_SCHEMA)


def downgrade() -> None:
    op.add_column(
        "games",
        sa.Column("owner", sa.String(), nullable=True),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_games_owner_type_mode", "games", ["owner", "game_type", "mode"], schema=_SCHEMA
    )

    op.drop_index("uq_games_daily", table_name="games", schema=_SCHEMA)
    op.create_index(
        "uq_games_daily_user",
        "games",
        ["daily_challenge_id", "user_id"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("daily_challenge_id IS NOT NULL AND user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_games_daily_owner",
        "games",
        ["daily_challenge_id", "owner"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("daily_challenge_id IS NOT NULL AND user_id IS NULL"),
    )

    op.alter_column("games", "user_id", nullable=True, schema=_SCHEMA)
