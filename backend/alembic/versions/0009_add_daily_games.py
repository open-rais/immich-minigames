"""add daily_configs, daily_challenges, games.daily_challenge_id

Daily games (Wordle-style: same content for every player each day, one attempt, its own
leaderboard) live in two new tables plus one new column, deliberately kept separate from every
existing table rather than overloading them:

`daily_configs` - one row per (game_type, mode), admin-owned - whether that mode participates in
the daily rotation (the "Activar juego diario" checkbox) plus its daily-only setting overrides.
Mirrors game_settings' existing one-row-per-(game_type,mode)-with-JSONB shape.

`daily_challenges` - one row per (day, game_type, mode) - the pre-generated content every player of
that mode plays that day, generated lazily on the first "Jugar daily" of the day (see
services/daily_service.py), plus a frozen settings snapshot so every player of the same day's
challenge plays under identical rules even if an admin changes a setting mid-day.

`games.daily_challenge_id` - NULL for every normal game (unchanged behavior); set only for a game
created through the daily flow, pointing at the challenge it was instantiated from. The two partial
unique indexes below enforce "one attempt per (challenge, player)" at the DB level - split by
ownership branch (like every other per-player games.py index) because Postgres doesn't treat two
NULLs as equal, so a single UNIQUE(daily_challenge_id, user_id) alone would never catch two
anonymous plays of the same challenge.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.create_table(
        "daily_configs",
        sa.Column("game_type", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("values", postgresql.JSONB(), nullable=False, server_default="{}"),
        schema=_SCHEMA,
    )

    op.create_table(
        "daily_challenges",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("challenge_date", sa.Date(), nullable=False),
        sa.Column("game_type", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("spec", postgresql.JSONB(), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "challenge_date", "game_type", "mode", name="uq_daily_challenges_date_type_mode"
        ),
        schema=_SCHEMA,
    )

    op.add_column(
        "games",
        sa.Column(
            "daily_challenge_id",
            postgresql.UUID(),
            sa.ForeignKey(f"{_SCHEMA}.daily_challenges.id"),
            nullable=True,
        ),
        schema=_SCHEMA,
    )
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


def downgrade() -> None:
    op.drop_index("uq_games_daily_owner", table_name="games", schema=_SCHEMA)
    op.drop_index("uq_games_daily_user", table_name="games", schema=_SCHEMA)
    op.drop_column("games", "daily_challenge_id", schema=_SCHEMA)
    op.drop_table("daily_challenges", schema=_SCHEMA)
    op.drop_table("daily_configs", schema=_SCHEMA)
