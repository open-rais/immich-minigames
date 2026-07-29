"""Player-facing daily-game endpoints (roadmap #G) - status listing + creating today's attempt.
Admin config lives in api/admin_daily_api.py; the leaderboard is added in F5. Mounted under
`/daily` by api/api.py (which is itself mounted at `/api/v1`, so the full path is
`/api/v1/daily/...`). Playing rounds reuses the existing `POST /games/{id}/rounds/{roundId}` and
`GET /games/{id}` routes unchanged - a daily game is a normal GameModel row underneath, just one
GamesService._row_to_game already knows how to rebuild with its frozen content
(services/games_service.py's _daily_game_kwargs)."""

from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from api.auth_api import get_current_user
from api.deps import get_games_service, get_owner_id
from api.dto.common import GameOut
from api.dto.daily import DailyStatusOut
from api.dto.leaderboard import DailyLeaderboardOut
from api.rate_limit import GAME_ACTION_LIMIT, limiter
from persistence.users import UserModel
from services.games_service import GamesService

router = APIRouter(prefix="/daily", tags=["daily"])


def _resets_at(today: date) -> datetime:
    # Server-local midnight of the day after `today` (decision [G], docs/TODO/DAILY-GAMES.md §4.6)
    # - naive datetimes throughout, matching the server-time convention GamesService.get_leaderboard
    # already uses for its own daily/weekly windows (Postgres's date_trunc('day', now())).
    return datetime.combine(today + timedelta(days=1), time.min)


@router.get("", response_model=DailyStatusOut)
def get_daily_status(
    owner: Annotated[str, Depends(get_owner_id)],
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> DailyStatusOut:
    today = date.today()
    statuses = games_service.get_daily_status(owner, user.id, today)
    return DailyStatusOut.from_statuses(_resets_at(today), datetime.now(), statuses)


@router.post("/{game_type}/{mode}/games", response_model=GameOut, status_code=201)
@limiter.limit(GAME_ACTION_LIMIT)
def create_daily_game(
    request: Request,
    game_type: str,
    mode: str,
    owner: Annotated[str, Depends(get_owner_id)],
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameOut:
    game = games_service.create_daily_game(owner=owner, game_type=game_type, mode=mode, user_id=user.id)
    return GameOut.from_game(game)


@router.get("/{game_type}/{mode}/leaderboard", response_model=DailyLeaderboardOut)
def get_daily_leaderboard(
    game_type: str,
    mode: str,
    games_service: Annotated[GamesService, Depends(get_games_service)],
    date_: Annotated[date | None, Query(alias="date")] = None,
) -> DailyLeaderboardOut:
    # No auth dependency of its own, but roadmap #H, F3's default-deny middleware now requires a
    # session for every route regardless - this route just never needed one on top of that.
    # Defaults to today; a date with no challenge for this (game_type, mode) just reads empty.
    challenge_date = date_ or date.today()
    entries = games_service.get_daily_leaderboard(game_type, mode, challenge_date)
    return DailyLeaderboardOut.from_entries(challenge_date, entries)
