"""
Own-database persistence for the daily-challenge feature. Two tables:

`DailyConfigModel` - one row per (game_type, mode), admin-owned - whether that mode participates in
the daily rotation (`enabled`, the "Activar juego diario" checkbox) plus its daily-only setting
overrides (`values`). Same one-row-per-(game_type,mode)-with-a-JSONB-payload shape as
persistence/game_settings.py's GameSettingsModel, just with an extra `enabled` column - a
(game_type, mode) with no row yet defaults to disabled with no overrides (see
services/daily_settings.py).

`DailyChallengeModel` - one row per (day, game_type, mode) - the pre-generated, shared content every
player of that mode plays that day (`spec`, shape documented per-game in
services/daily_challenge_service.py) plus a frozen snapshot of that day's effective settings
(`settings`, snapshotted rather than read live like a normal game's settings). Referenced by
persistence/games.py's GameModel.daily_challenge_id.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base


class DailyConfigModel(Base):
    __tablename__ = "daily_configs"

    game_type: Mapped[str] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    values: Mapped[dict] = mapped_column(JSONB, default=dict)


class DailyChallengeModel(Base):
    __tablename__ = "daily_challenges"
    __table_args__ = (
        UniqueConstraint("challenge_date", "game_type", "mode", name="uq_daily_challenges_date_type_mode"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    challenge_date: Mapped[date] = mapped_column(Date)
    game_type: Mapped[str]
    mode: Mapped[str]
    spec: Mapped[dict] = mapped_column(JSONB)
    settings: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
