"""REST API entrypoint - routes are mounted here.

Routes don't catch this app's own domain exceptions (GameNotFoundError etc.) - those propagate to
the app-level handlers registered in main.py, which is the single place mapping them to HTTP
status codes."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError

from api.admin_api import router as admin_router
from api.admin_daily_api import router as admin_daily_router
from api.admin_games_api import router as admin_games_router
from api.admin_invites_api import router as admin_invites_router
from api.auth_api import get_current_user
from api.auth_api import router as auth_router
from api.daily_api import router as daily_router
from api.deps import get_games_service, get_immich_service, get_owner_id
from api.dto.common import CreateGameIn, CurrentGameOut, GameOut, PlayRoundOut, RecentGamesOut, parse_guess
from api.dto.config import ConfigOut
from api.dto.leaderboard import LeaderboardOut, LeaderboardWindow
from api.dto.persons import PersonSearchOut
from api.dto.records import GameRecordsOut
from api.rate_limit import GAME_ACTION_LIMIT, SEARCH_LIMIT, THUMBNAIL_LIMIT, limiter
from config import Settings, get_settings
from persistence.users import UserModel
from services.games_service import GamesService
from services.immich_service import ImmichService

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(admin_games_router)
router.include_router(admin_daily_router)
router.include_router(admin_invites_router)
router.include_router(daily_router)


@router.get("/config", response_model=ConfigOut)
def get_config(settings: Annotated[Settings, Depends(get_settings)]) -> ConfigOut:
    # No rate limit of its own (static config, no DB/Immich call) - used by the frontend's "Ver en
    # Immich" buttons (ROUNDS-VIEW.md roadmap point #10). Requires a session like everything else
    # now (roadmap #H, F3's default-deny middleware), even though this route declares no auth
    # dependency itself. Depends() rather than calling get_settings() inline (see auth_api.py) so
    # tests can override this one dependency without touching the lru_cache singleton every other
    # module shares.
    return ConfigOut(immich_external_url=settings.immich_public_url)


@router.post("/games", response_model=GameOut, status_code=201)
@limiter.limit(GAME_ACTION_LIMIT)
def create_game(
    request: Request,
    body: CreateGameIn,
    owner: Annotated[str, Depends(get_owner_id)],
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameOut:
    # Roadmap #H, F3 - every request reaching here is now guaranteed authenticated (the
    # default-deny middleware already rejected anything without a valid session), so `user` is
    # never None anymore - get_current_user_optional is gone. owner/X-Owner-Id stays exactly as
    # before (GamesService's own owner/user_id plumbing is untouched until F4).
    game = games_service.create_game(owner=owner, game_type=body.type, mode=body.mode, user_id=user.id)
    return GameOut.from_game(game)


@router.get("/games/records", response_model=GameRecordsOut)
def get_game_records(
    owner: Annotated[str, Depends(get_owner_id)],
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameRecordsOut:
    records = games_service.get_personal_records(owner, user.id)
    return GameRecordsOut.from_records(records)


@router.get("/games/current", response_model=CurrentGameOut)
def get_current_game(
    game_type: str,
    mode: str,
    owner: Annotated[str, Depends(get_owner_id)],
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> CurrentGameOut:
    # Idle-screen "Continuar" lookup (roadmap #e). Declared before GET /games/{game_id} (same
    # reason /games/records already is): a static path must precede a {game_id}: UUID catch-all or
    # it 422s trying to parse "current" as a UUID.
    game = games_service.get_current_game(owner, game_type, mode, user.id)
    return CurrentGameOut.from_game(game)


@router.get("/games/recent", response_model=RecentGamesOut)
def get_recent_games(
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> RecentGamesOut:
    # "Ver juegos" profile modal (roadmap #e) - login required (unlike get_current_game above),
    # matching the roadmap's "del jugador con sesión iniciada" - there's no anonymous equivalent of
    # a persistent game history to look up.
    games = games_service.get_recent_games(user.id)
    return RecentGamesOut.from_recent_games(games)


@router.get("/games/{game_type}/{mode}/leaderboard", response_model=LeaderboardOut)
def get_leaderboard(
    game_type: str,
    mode: str,
    games_service: Annotated[GamesService, Depends(get_games_service)],
    window: LeaderboardWindow = "all",
) -> LeaderboardOut:
    # No auth dependency of its own, but roadmap #H, F3's default-deny middleware now requires a
    # session for every route regardless ("sin sesión no se ve nada: ni... leaderboards", see
    # docs/TODO/NEW-AUTH.md §2) - this route just never needed one on top of that.
    entries = games_service.get_leaderboard(game_type, mode, window)
    return LeaderboardOut.from_entries(window, entries)


@router.get("/games/{game_id}", response_model=GameOut)
def get_game(
    game_id: UUID,
    owner: Annotated[str, Depends(get_owner_id)],
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameOut:
    game = games_service.get_game(game_id, owner, user)
    return GameOut.from_game(game)


@router.post("/games/{game_id}/rounds/{round_id}", response_model=PlayRoundOut)
@limiter.limit(GAME_ACTION_LIMIT)
def play_round(
    request: Request,
    game_id: UUID,
    round_id: UUID,
    body: Annotated[dict[str, Any], Body()],
    owner: Annotated[str, Depends(get_owner_id)],
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> PlayRoundOut:
    # game_id already fixes this round's game/mode - looked up first so the guess body only ever
    # needs to hold the guess itself, not also restate a game_type the client could get wrong.
    existing_game = games_service.get_game(game_id, owner, user)
    try:
        guess = parse_guess(existing_game.current_round, body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    game = games_service.play_loaded_round(existing_game, round_id, guess)
    answered_round = next(r for r in game.rounds if r.id == round_id)
    return PlayRoundOut.from_answered(game, answered_round)


def _proxy_thumbnail(fetch: Callable[[], tuple[bytes, str]]) -> Response:
    """Runs an ImmichService thumbnail fetch and maps its httpx errors to HTTP responses - shared by
    the person and asset thumbnail endpoints, which only differ in which fetch they call."""
    try:
        content, content_type = fetch()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            # Immich rejected the request itself (bad/expired IMMICH_API_KEY) - a config problem, not
            # "this particular entity has no photo". Keep that distinct from a plain 404 so it doesn't
            # get misread as normal missing-thumbnail data.
            raise HTTPException(status_code=502, detail="Immich rejected the request - check IMMICH_API_KEY") from exc
        raise HTTPException(status_code=404, detail="thumbnail not found") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="could not reach Immich") from exc
    return Response(content=content, media_type=content_type)


@router.get("/persons/search", response_model=PersonSearchOut)
@limiter.limit(SEARCH_LIMIT)
def search_persons(
    request: Request,
    query: Annotated[str, Query(min_length=1)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 3,
) -> PersonSearchOut:
    # Reusable across features (not just Immichdle's guess input, see games/immichdle.py) - a
    # single-letter query is enough, matching is word-prefix (not substring), and results page in
    # small batches (default 3) for infinite-scroll UIs. See ImmichService.search_persons.
    persons = immich_service.search_persons(query, offset=offset, limit=limit)
    return PersonSearchOut.from_persons(persons)


@router.get("/people/{person_id}/thumbnail")
@limiter.limit(THUMBNAIL_LIMIT)
def get_person_thumbnail(
    request: Request,
    person_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    return _proxy_thumbnail(lambda: immich_service.get_person_thumbnail(person_id))


@router.get("/assets/{asset_id}/thumbnail")
@limiter.limit(THUMBNAIL_LIMIT)
def get_asset_thumbnail(
    request: Request,
    asset_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    return _proxy_thumbnail(lambda: immich_service.get_asset_thumbnail(asset_id))


@router.get("/albums/{album_id}/thumbnail")
@limiter.limit(THUMBNAIL_LIMIT)
def get_album_thumbnail(
    request: Request,
    album_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    # An album has no thumbnail of its own - its cover is one of its assets (Immich's chosen cover,
    # or the first asset as a fallback), whose bytes are then served like any other asset thumbnail.
    cover_asset_id = immich_service.get_album_cover_asset_id(album_id)
    if cover_asset_id is None:
        raise HTTPException(status_code=404, detail="album has no cover")
    return _proxy_thumbnail(lambda: immich_service.get_asset_thumbnail(cover_asset_id))
