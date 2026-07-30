"""Leaderboard DTOs (roadmap point F, see GamesService.get_leaderboard) plus the daily-challenge
leaderboard (roadmap point #G, F5 - see GamesService.get_daily_leaderboard)."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from services.games_service import LeaderboardEntry

LeaderboardWindow = Literal["all", "weekly", "daily"]


class LeaderboardEntryOut(BaseModel):
    rank: int
    username: str
    skin_person_id: UUID | None
    best_score: int

    @classmethod
    def from_entry(cls, entry: LeaderboardEntry) -> "LeaderboardEntryOut":
        return cls(
            rank=entry.rank,
            username=entry.username,
            skin_person_id=entry.skin_person_id,
            best_score=entry.best_score,
        )


class LeaderboardOut(BaseModel):
    window: LeaderboardWindow
    entries: list[LeaderboardEntryOut]

    @classmethod
    def from_entries(cls, window: LeaderboardWindow, entries: list[LeaderboardEntry]) -> "LeaderboardOut":
        return cls(window=window, entries=[LeaderboardEntryOut.from_entry(e) for e in entries])


class DailyLeaderboardOut(BaseModel):
    date: date
    entries: list[LeaderboardEntryOut]

    @classmethod
    def from_entries(cls, challenge_date: date, entries: list[LeaderboardEntry]) -> "DailyLeaderboardOut":
        return cls(date=challenge_date, entries=[LeaderboardEntryOut.from_entry(e) for e in entries])
