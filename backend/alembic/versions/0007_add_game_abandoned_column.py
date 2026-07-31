"""add games.abandoned column

`finished` keeps its exact current meaning (game ended per its own rules). `abandoned` is a new,
orthogonal terminal state: set when the player starts a new game of the same (owner-or-user,
game_type, mode) while a previous one was still unfinished (see
GamesService._abandon_active_games). "Active/resumable" = finished IS FALSE AND abandoned IS FALSE.
Existing rows backfill to False - every pre-existing unfinished game becomes resumable the moment
this ships, which is the bug being fixed, not a state to migrate away from.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-28

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("abandoned", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("games", "abandoned", schema=_SCHEMA)
