"""REST API entrypoint - routes are mounted here.

Routes don't catch this app's own domain exceptions (GameNotFoundError etc.) - those propagate to
the app-level handlers registered in main.py, which is the single place mapping them to HTTP
status codes."""

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.auth_api import router as auth_router
from api.deps import get_db_session
from api.schemas import CreateGameIn, GameOut, PlayRoundOut, parse_guess
from services.games_service import GamesService
from services.immich_service import ImmichService

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)


@lru_cache(maxsize=1)
def get_immich_service() -> ImmichService:
    return ImmichService()


def get_games_service(
    session: Annotated[Session, Depends(get_db_session)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> GamesService:
    return GamesService(session, immich_service)


def get_owner_id(x_owner_id: Annotated[str, Header()]) -> str:
    return x_owner_id


@router.post("/games", response_model=GameOut, status_code=201)
def create_game(
    body: CreateGameIn,
    owner: Annotated[str, Depends(get_owner_id)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameOut:
    game = games_service.create_game(owner=owner, game_type=body.type, mode=body.mode)
    return GameOut.from_game(game)


@router.get("/games/{game_id}", response_model=GameOut)
def get_game(
    game_id: UUID,
    owner: Annotated[str, Depends(get_owner_id)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameOut:
    game = games_service.get_game(game_id, owner)
    return GameOut.from_game(game)


@router.post("/games/{game_id}/rounds/{round_id}", response_model=PlayRoundOut)
def play_round(
    game_id: UUID,
    round_id: UUID,
    body: Annotated[dict[str, Any], Body()],
    owner: Annotated[str, Depends(get_owner_id)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> PlayRoundOut:
    # game_id already fixes this round's game/mode - looked up first so the guess body only ever
    # needs to hold the guess itself, not also restate a game_type the client could get wrong.
    existing_game = games_service.get_game(game_id, owner)
    try:
        guess = parse_guess(existing_game.game_type, existing_game.mode, body)
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


@router.get("/people/{person_id}/thumbnail")
def get_person_thumbnail(
    person_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    return _proxy_thumbnail(lambda: immich_service.get_person_thumbnail(person_id))


@router.get("/assets/{asset_id}/thumbnail")
def get_asset_thumbnail(
    asset_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    return _proxy_thumbnail(lambda: immich_service.get_asset_thumbnail(asset_id))
