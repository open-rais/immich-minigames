"""Shared FastAPI dependencies used by more than one router (api/api.py, api/auth_api.py)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.orm import Session

from persistence.base import get_session_factory
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
