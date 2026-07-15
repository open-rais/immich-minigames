"""add games.user_id and users.skin_person_id (roadmap point E)

Both columns are nullable, so existing rows need no backfill: games.user_id stays null for
anonymous play (see services/games_service.py), users.skin_person_id stays null until an account
picks a cosmetic avatar.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{_SCHEMA}.users.id"), nullable=True),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_games_owner_type_mode", "games", ["owner", "game_type", "mode"], schema=_SCHEMA
    )
    op.create_index(
        "ix_games_user_type_mode", "games", ["user_id", "game_type", "mode"], schema=_SCHEMA
    )
    op.add_column(
        "users",
        sa.Column("skin_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("users", "skin_person_id", schema=_SCHEMA)
    op.drop_index("ix_games_user_type_mode", table_name="games", schema=_SCHEMA)
    op.drop_index("ix_games_owner_type_mode", table_name="games", schema=_SCHEMA)
    op.drop_column("games", "user_id", schema=_SCHEMA)
