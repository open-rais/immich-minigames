"""Admin feature (ADMIN-FEATURE.md point #4) - per-game_type admin overrides for the scoring/
difficulty constants each games/*.py module defines as its default (see services/game_settings.py
for the registry of which keys are configurable and what those defaults are). One row per
game_type; a game_type with no row (or a key missing from its `values` JSONB) just falls back to
that module's hardcoded default - "reset to defaults" is deleting the row/key, not writing the
default value back out. Same "one table + JSONB payload" shape as persistence/games.py's
RoundModel.payload, rather than a typed column per setting.
"""

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base


class GameSettingsModel(Base):
    __tablename__ = "game_settings"

    game_type: Mapped[str] = mapped_column(primary_key=True)
    values: Mapped[dict] = mapped_column(JSONB, default=dict)
