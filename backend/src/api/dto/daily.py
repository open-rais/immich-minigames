"""Daily-game player-facing status DTOs (see services/daily_games_service.py's
DailyGamesService.get_daily_status/create_daily_game). Admin config DTOs live in api/dto/admin.py;
the leaderboard DTO lives in api/dto/leaderboard.py."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from services.daily_games_service import DailyModeStatus

DailyModeStatusValue = Literal["not_played", "in_progress", "finished"]


class DailyModeStatusOut(BaseModel):
    game_type: str
    mode: str
    status: DailyModeStatusValue
    game_id: UUID | None
    score: int | None

    @classmethod
    def from_status(cls, status: DailyModeStatus) -> "DailyModeStatusOut":
        return cls(
            game_type=status.game_type,
            mode=status.mode,
            status=status.status,
            game_id=status.game_id,
            score=status.score,
        )


class DailyStatusOut(BaseModel):
    # ISO datetimes (server time) - the frontend's countdown ticks off the offset
    # between these two rather than trusting its own clock alone.
    resets_at: datetime
    server_now: datetime
    modes: list[DailyModeStatusOut]

    @classmethod
    def from_statuses(
        cls, resets_at: datetime, server_now: datetime, statuses: list[DailyModeStatus]
    ) -> "DailyStatusOut":
        return cls(
            resets_at=resets_at, server_now=server_now, modes=[DailyModeStatusOut.from_status(s) for s in statuses]
        )
