"""Shared FastAPI dependencies used by more than one router (api/api.py, api/auth_api.py)."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from persistence.base import get_session_factory

_session_factory = get_session_factory()


def get_db_session() -> Iterator[Session]:
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
