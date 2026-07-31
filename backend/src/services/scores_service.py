"""Score/history reporting - personal records (roadmap point E), leaderboards (roadmap point F,
normal + daily), and the profile's recent-games list (roadmap #e). Every query is read-only against
persistence/games_repository.py's GameRepository; unlike services/games_service.py and
services/daily_games_service.py, this service never builds or mutates a BaseGame, so it has no
dependency on services/game_factory.py.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from games.registry import GAMES
from persistence.games_repository import GameRepository
from services.errors import UnsupportedGameError


@dataclass(frozen=True)
class GameRecord:
    """One personal-best entry (roadmap point E) - a mode the account has at least one finished
    game for, with their highest score in it."""

    game_type: str
    mode: str
    best_score: int


@dataclass(frozen=True)
class RecentGame:
    """One row of the profile's "Ver juegos" modal (roadmap point #e) - a logged-in account's last
    N games that reached a final state, either by finishing naturally or by being abandoned when
    the player started a new one of that (game_type, mode). A still-active game never appears here
    - see ScoresService.get_recent_games."""

    id: UUID
    game_type: str
    mode: str
    score: int
    finished: bool
    abandoned: bool
    created_at: datetime
    # Whether this was a daily-challenge game rather than a normal one. Unlike every other
    # per-player query in this file, get_recent_games doesn't filter daily games out (it's personal
    # history, not a score comparison) - it just flags them so the "Ver juegos" modal can label them
    # (see docs/TODO/DAILY-GAMES.md §4.5).
    is_daily: bool


@dataclass(frozen=True)
class LeaderboardEntry:
    """One leaderboard row (roadmap point F) - a distinct account's best score for a (game_type,
    mode) within a time window, 1-indexed by rank."""

    rank: int
    username: str
    skin_person_id: UUID | None
    best_score: int


class ScoresService:
    def __init__(self, repository: GameRepository) -> None:
        self._repository = repository

    def get_personal_records(self, user_id: UUID) -> list[GameRecord]:
        """Roadmap point E - personal-best score per (game_type, mode), shown in the main menu -
        every game's score is higher-is-better (see games/shared/scoring.py's exp_decay_score and
        each game's win/streak-based deltas), so MAX(score) among finished games is a valid "best"
        for every existing game/mode."""
        rows = self._repository.personal_records(user_id)
        return [GameRecord(game_type=gt, mode=m, best_score=best) for gt, m, best in rows]

    def get_leaderboard(
        self, game_type: str, mode: str, window: Literal["all", "weekly", "daily"]
    ) -> list[LeaderboardEntry]:
        """Roadmap point F - top 15 distinct accounts by their best score for this (game_type,
        mode), optionally restricted to games created since this week's/today's midnight (server
        time, computed in Postgres so the cutoff is never skewed by a client/server clock or
        timezone mismatch)."""
        if (game_type, mode) not in GAMES:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")
        rows = self._repository.leaderboard_rows(game_type, mode, window)
        return [
            LeaderboardEntry(rank=rank, username=username, skin_person_id=skin_person_id, best_score=score)
            for rank, (username, skin_person_id, score) in enumerate(rows, start=1)
        ]

    def get_daily_leaderboard(self, game_type: str, mode: str, challenge_date: date) -> list[LeaderboardEntry]:
        """Roadmap #G, F5 - top 15 accounts by score for *one specific day's* challenge, not a
        rolling window like get_leaderboard's all/weekly/daily - a date with no challenge for this
        (game_type, mode) simply has no entries, not an error."""
        if (game_type, mode) not in GAMES:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")

        challenge_id = self._repository.daily_challenge_id(game_type, mode, challenge_date)
        if challenge_id is None:
            return []

        rows = self._repository.daily_leaderboard_rows(challenge_id)
        return [
            LeaderboardEntry(rank=rank, username=username, skin_person_id=skin_person_id, best_score=score)
            for rank, (username, skin_person_id, score) in enumerate(rows, start=1)
        ]

    def get_recent_games(self, user_id: UUID, limit: int = 5) -> list[RecentGame]:
        """ "Ver juegos" profile modal (roadmap #e) - a logged-in player's last `limit` games that
        reached a final state (finished naturally, or abandoned by starting a new one), most recent
        first. A game still actively in progress is intentionally excluded - it belongs on that
        mode's idle screen as "Continuar", not in this history list."""
        rows = self._repository.get_recent(user_id, limit)
        return [
            RecentGame(
                id=row.id,
                game_type=row.game_type,
                mode=row.mode,
                score=row.score,
                finished=row.finished,
                abandoned=row.abandoned,
                created_at=row.created_at,
                is_daily=row.daily_challenge_id is not None,
            )
            for row in rows
        ]
