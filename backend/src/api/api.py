"""REST API entrypoint - routes are mounted here."""

from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from api.schemas import CreateGameIn, GameOut, PlayRoundIn, PlayRoundOut
from persistance.games import get_session_factory
from services.games_service import (
    GameNotFoundError,
    GameOwnershipError,
    GamesService,
    RoundNotPendingError,
    UnsupportedGameError,
)
from services.immich_service import ImmichService

router = APIRouter(prefix="/api/v1")

_session_factory = get_session_factory()


def get_db_session() -> Iterator[Session]:
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


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
    try:
        game = games_service.create_game(owner=owner, game_type=body.type, mode=body.mode)
    except UnsupportedGameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GameOut.from_game(game)


@router.get("/games/{game_id}", response_model=GameOut)
def get_game(
    game_id: UUID,
    owner: Annotated[str, Depends(get_owner_id)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> GameOut:
    try:
        game = games_service.get_game(game_id, owner)
    except GameNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GameOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return GameOut.from_game(game)


@router.post("/games/{game_id}/rounds/{round_id}", response_model=PlayRoundOut)
def play_round(
    game_id: UUID,
    round_id: UUID,
    body: PlayRoundIn,
    owner: Annotated[str, Depends(get_owner_id)],
    games_service: Annotated[GamesService, Depends(get_games_service)],
) -> PlayRoundOut:
    try:
        game = games_service.play_round(game_id, owner, round_id, body.guess)
    except GameNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GameOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RoundNotPendingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    answered_round = next(r for r in game.rounds if r.id == round_id)
    return PlayRoundOut.from_answered(game, answered_round)
