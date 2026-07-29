"""add game_settings.mode column, composite (game_type, mode) primary key (roadmap point #f)

Roadmap #f splits the admin "Juegos" accordion into one top-level accordion per game with a
nested row per mode (see admin/AdminGamesSection.tsx) - each mode now needs its own independently
overridable settings row instead of sharing one row per game_type. MoreOrLess is the only game
with more than one mode today (personAssets/albumAssets) and has never had a persisted row (its
spec list is empty - update_settings always raises UnknownGameSettingError for it, see
services/game_settings.py), so there's nothing to backfill for it; the four other games each have
exactly one mode today, so their existing game_type-keyed row maps 1:1 onto that one real mode
with zero ambiguity. The (game_type -> mode) pairs below are hardcoded literal strings rather than
imported from games/*.py's MODE_* constants - migrations in this repo are self-contained and never
import app code (see 0006_add_person_face_embedding_cache.py). scripts/migrate_legacy_schema.py
needs a matching, separately-hardcoded fix (see its own docstring) since a legacy pre-split schema
is permanently frozen at the pre-`mode` shape and can never gain this column on its own.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-28

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"

# game_type -> its one pre-existing mode (see module docstring). Verified literal strings against
# games/geoguessr.py, dateguessr.py, immichdle.py, whos_that_person.py's MODE_* constants.
_EXISTING_SINGLE_MODE = {
    "geoguessr": "distanceBetweenGuess",
    "dateguessr": "daysToDate",
    "immichdle": "person",
    "whos-that-person": "namedFaces",
}


def upgrade() -> None:
    op.add_column("game_settings", sa.Column("mode", sa.String(), nullable=True), schema=_SCHEMA)

    game_settings = sa.table(
        "game_settings",
        sa.column("game_type", sa.String()),
        sa.column("mode", sa.String()),
        schema=_SCHEMA,
    )
    for game_type, mode in _EXISTING_SINGLE_MODE.items():
        op.execute(game_settings.update().where(game_settings.c.game_type == game_type).values(mode=mode))

    # Any row whose game_type wasn't one of the four above (there shouldn't be any - see module
    # docstring) is left NULL here, so this fails loudly instead of silently landing a bad row.
    op.alter_column("game_settings", "mode", nullable=False, schema=_SCHEMA)

    op.drop_constraint("game_settings_pkey", "game_settings", schema=_SCHEMA, type_="primary")
    op.create_primary_key("game_settings_pkey", "game_settings", ["game_type", "mode"], schema=_SCHEMA)


def downgrade() -> None:
    op.drop_constraint("game_settings_pkey", "game_settings", schema=_SCHEMA, type_="primary")
    op.create_primary_key("game_settings_pkey", "game_settings", ["game_type"], schema=_SCHEMA)
    op.drop_column("game_settings", "mode", schema=_SCHEMA)
