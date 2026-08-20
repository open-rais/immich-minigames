"""REST API entrypoint - routes are mounted here.

Routes don't catch this app's own domain exceptions (GameNotFoundError etc.) - those propagate to
the app-level handlers registered in main.py, which is the single place mapping them to HTTP
status codes."""

import hashlib
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.admin_api import router as admin_router
from api.admin_daily_api import router as admin_daily_router
from api.admin_games_api import router as admin_games_router
from api.admin_invites_api import router as admin_invites_router
from api.admin_workers_api import router as admin_workers_router
from api.auth_api import get_current_user
from api.auth_api import router as auth_router
from api.daily_api import router as daily_router
from api.deps import get_db_session, get_games_service, get_immich_service, get_scores_service
from api.dto.albums import AlbumSearchOut
from api.dto.common import CreateGameIn, CurrentGameOut, GameOut, PlayRoundOut, RecentGamesOut, parse_guess
from api.dto.config import ConfigOut
from api.dto.health import HealthOut
from api.dto.leaderboard import LeaderboardOut, LeaderboardWindow
from api.dto.persons import PersonSearchOut
from api.dto.records import GameRecordsOut
from api.rate_limit import GAME_ACTION_LIMIT, SEARCH_LIMIT, THUMBNAIL_LIMIT, limiter
from api.reports_api import router as reports_router
from config import Settings, get_settings
from persistence.users import UserModel
from services.games_service import GamesService
from services.immich import ImmichService
from services.scores_service import ScoresService

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(admin_games_router)
router.include_router(admin_daily_router)
router.include_router(admin_invites_router)
router.include_router(admin_workers_router)
router.include_router(daily_router)
router.include_router(reports_router)


@router.get("/health", response_model=HealthOut)
def health_check(session: Annotated[Session, Depends(get_db_session)]) -> HealthOut:
    # Allow-listed in auth_middleware.py (Docker's healthcheck request carries no session cookie).
    # Checks only this app's own DB, not Immich's - mixing the two would make this container
    # report unhealthy for a problem that isn't its own.
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return HealthOut(status="ok")


@router.get("/config", response_model=ConfigOut)
def get_config(settings: Annotated[Settings, Depends(get_settings)]) -> ConfigOut:
    # No rate limit of its own (static config, no DB/Immich call) - used by the frontend's "Ver en
    # Immich" buttons. Requires a session like everything else now (the default-deny middleware),
    # even though this route declares no auth dependency itself. Depends() rather than calling
    # get_settings() inline (see auth_api.py) so
    # tests can override this one dependency without touching the lru_cache singleton every other
    # module shares.
    return ConfigOut(immich_external_url=settings.immich_public_url)


@router.post("/games", response_model=GameOut, status_code=201)
@limiter.limit(GAME_ACTION_LIMIT)
def create_game(
    request: Request,
    body: CreateGameIn,
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameOut:
    game = games_service.create_game(game_type=body.type, mode=body.mode, user_id=user.id)
    return GameOut.from_game(game)


@router.get("/games/records", response_model=GameRecordsOut)
def get_game_records(
    user: Annotated[UserModel, Depends(get_current_user)],
    scores_service: Annotated[ScoresService, Depends(get_scores_service)],
) -> GameRecordsOut:
    records = scores_service.get_personal_records(user.id)
    return GameRecordsOut.from_records(records)


@router.get("/games/current", response_model=CurrentGameOut)
def get_current_game(
    game_type: str,
    mode: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> CurrentGameOut:
    # Idle-screen "Continuar" lookup. Declared before GET /games/{game_id} (same
    # reason /games/records already is): a static path must precede a {game_id}: UUID catch-all or
    # it 422s trying to parse "current" as a UUID.
    game = games_service.get_current_game(game_type, mode, user.id)
    return CurrentGameOut.from_game(game)


@router.get("/games/recent", response_model=RecentGamesOut)
def get_recent_games(
    user: Annotated[UserModel, Depends(get_current_user)],
    scores_service: Annotated[ScoresService, Depends(get_scores_service)],
) -> RecentGamesOut:
    # "Ver juegos" profile modal - login required (unlike get_current_game above): there's no
    # anonymous equivalent of a persistent game history to look up.
    games = scores_service.get_recent_games(user.id)
    return RecentGamesOut.from_recent_games(games)


@router.get("/games/{game_type}/{mode}/leaderboard", response_model=LeaderboardOut)
def get_leaderboard(
    game_type: str,
    mode: str,
    scores_service: Annotated[ScoresService, Depends(get_scores_service)],
    window: LeaderboardWindow = "all",
) -> LeaderboardOut:
    # No auth dependency of its own, but the default-deny middleware now requires a session for
    # every route regardless - this route just never needed one on top of that.
    entries = scores_service.get_leaderboard(game_type, mode, window)
    return LeaderboardOut.from_entries(window, entries)


@router.get("/games/{game_id}", response_model=GameOut)
def get_game(
    game_id: UUID,
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameOut:
    game = games_service.get_game(game_id, user)
    return GameOut.from_game(game)


@router.post("/games/{game_id}/rounds/{round_id}", response_model=PlayRoundOut)
@limiter.limit(GAME_ACTION_LIMIT)
def play_round(
    request: Request,
    game_id: UUID,
    round_id: UUID,
    body: Annotated[dict[str, Any], Body()],
    user: Annotated[UserModel, Depends(get_current_user)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> PlayRoundOut:
    # game_id already fixes this round's game/mode - looked up first so the guess body only ever
    # needs to hold the guess itself, not also restate a game_type the client could get wrong.
    existing_game = games_service.get_game(game_id, user)
    try:
        guess = parse_guess(existing_game.current_round, body)
    except ValidationError as exc:
        # include_context=False - a custom `raise ValueError(...)` inside a guess schema's own
        # validator (TimelinePlayRoundIn's board-length check) otherwise leaves the raw exception
        # object in errors()[i]["ctx"]["error"], which isn't JSON-serializable and 500s the response
        # instead of returning this 422.
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False)) from exc

    game = games_service.play_loaded_round(existing_game, round_id, guess)
    answered_round = next(r for r in game.rounds if r.id == round_id)
    return PlayRoundOut.from_answered(game, answered_round)


# Fixed, not env-configurable yet (single-user/household app. max-age is short on purpose - disk/bandwidth aren't a
# real concern at this app's scale, so there's no reason not to revalidate often; stale-while-
# revalidate is what actually keeps thumbnails feeling instant past that point, by letting the
# browser serve the cached copy immediately and refresh it in the background instead of blocking on a
# new response
_THUMBNAIL_MAX_AGE_SECONDS = 30 * 60
_THUMBNAIL_STALE_WHILE_REVALIDATE_SECONDS = 24 * 60 * 60


def _proxy_thumbnail(request: Request, fetch: Callable[[], tuple[bytes, str]]) -> Response:
    """Runs an ImmichService thumbnail fetch and maps its httpx errors to HTTP responses - shared by
    the person and asset thumbnail endpoints, which only differ in which fetch they call.

    Adds Cache-Control/ETag so the browser (native <img> and the frontend's own fetch-based thumbnail
    queue alike) can skip re-downloading bytes it already has The ETag is computed here from the fetched
    bytes rather than forwarded from Immich's own response - Immich isn't confirmed to send one on these
    endpoints, and computing it ourselves works regardless."""
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

    etag = hashlib.sha1(content).hexdigest()  # noqa: S324 - cache validator, not security-sensitive
    headers = {
        "Cache-Control": f"private, max-age={_THUMBNAIL_MAX_AGE_SECONDS}, "
        f"stale-while-revalidate={_THUMBNAIL_STALE_WHILE_REVALIDATE_SECONDS}",
        "ETag": etag,
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=content, media_type=content_type, headers=headers)


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


@router.get("/albums/search", response_model=AlbumSearchOut)
@limiter.limit(SEARCH_LIMIT)
def search_albums(
    request: Request,
    query: Annotated[str, Query(min_length=1)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 3,
) -> AlbumSearchOut:
    # Albumdle's guess-input autocomplete (roadmap #14) - mirrors search_persons above exactly.
    # See ImmichService.search_albums.
    albums = immich_service.search_albums(query, offset=offset, limit=limit)
    return AlbumSearchOut.from_albums(albums)


@router.get("/people/{person_id}/thumbnail")
@limiter.limit(THUMBNAIL_LIMIT)
def get_person_thumbnail(
    request: Request,
    person_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    return _proxy_thumbnail(request, lambda: immich_service.get_person_thumbnail(person_id))


@router.get("/assets/{asset_id}/thumbnail")
@limiter.limit(THUMBNAIL_LIMIT)
def get_asset_thumbnail(
    request: Request,
    asset_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    return _proxy_thumbnail(request, lambda: immich_service.get_asset_thumbnail(asset_id))


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
    return _proxy_thumbnail(request, lambda: immich_service.get_asset_thumbnail(cover_asset_id))
