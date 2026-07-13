"""REST API entrypoint - routes are mounted here.

Routes don't catch this app's own domain exceptions (GameNotFoundError etc.) - those propagate to
the app-level handlers registered in main.py, which is the single place mapping them to HTTP
status codes."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.schemas import CreateGameIn, GameOut, PlayRoundOut, parse_guess
from persistance.games import get_session_factory
from services.games_service import GamesService
from services.immich_service import ImmichService

router = APIRouter(prefix="/api/v1")

_session_factory = get_session_factory()


def get_db_session() -> Iterator[Session]:
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


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

    game = games_service.play_round(game_id, owner, round_id, guess)
    answered_round = next(r for r in game.rounds if r.id == round_id)
    return PlayRoundOut.from_answered(game, answered_round)


@router.get("/people/{person_id}/thumbnail")
def get_person_thumbnail(
    person_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    try:
        content, content_type = immich_service.get_person_thumbnail(person_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            # Immich rejected the request itself (bad/expired IMMICH_API_KEY) - a config problem,
            # not "this particular person has no photo". Keep that distinct from a plain 404 so it
            # doesn't get misread as normal missing-thumbnail data.
            raise HTTPException(status_code=502, detail="Immich rejected the request - check IMMICH_API_KEY") from exc
        raise HTTPException(status_code=404, detail="thumbnail not found") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="could not reach Immich") from exc
    return Response(content=content, media_type=content_type)


@router.get("/assets/{asset_id}/thumbnail")
def get_asset_thumbnail(
    asset_id: UUID,
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> Response:
    try:
        content, content_type = immich_service.get_asset_thumbnail(asset_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=502, detail="Immich rejected the request - check IMMICH_API_KEY") from exc
        raise HTTPException(status_code=404, detail="thumbnail not found") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="could not reach Immich") from exc
    return Response(content=content, media_type=content_type)
