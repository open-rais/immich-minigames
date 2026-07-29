"""Shared FastAPI dependencies used by more than one router (api/api.py, api/auth_api.py,
api/daily_api.py)."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from persistence.base import get_session_factory
from services.games_service import GamesService
from services.immich_service import ImmichService
from services.ml_service import MLService

_session_factory = get_session_factory()


def get_db_session() -> Iterator[Session]:
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


# Moved here (from api/api.py) so api/auth_api.py can also depend on ImmichService (to validate a
# skin's person_id, see PUT /auth/me/skin) without a circular import - api.py already imports
# auth_api.py's router, so the reverse import would loop.
@lru_cache(maxsize=1)
def get_immich_service() -> ImmichService:
    return ImmichService()


@lru_cache(maxsize=1)
def get_ml_service() -> MLService:
    return MLService()


def get_owner_id(x_owner_id: Annotated[str, Header()]) -> str:
    return x_owner_id


# Roadmap #G - moved here (rather than staying private to api/api.py, as it originally was) so
# api/daily_api.py can also depend on it without api.py <-> daily_api.py becoming a circular import
# (api.py already imports daily_api.py's router to mount it).
def get_games_service(
    session: Annotated[Session, Depends(get_db_session)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
    ml_service: Annotated[MLService, Depends(get_ml_service)],
) -> GamesService:
    return GamesService(session, immich_service, ml_service)
