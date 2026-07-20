"""add game_settings table (ADMIN-FEATURE.md point #4)

One row per game_type, `values` JSONB holds only the overridden keys - a game_type with no row
(or a key missing from `values`) falls back to that game module's hardcoded default, see
services/game_settings.py.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.create_table(
        "game_settings",
        sa.Column("game_type", sa.String(), primary_key=True),
        sa.Column("values", postgresql.JSONB(), nullable=False, server_default="{}"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("game_settings", schema=_SCHEMA)
