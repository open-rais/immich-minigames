"""
These are integration tests against the real dev Immich Postgres brought up by
docker-compose.yml (see docs/ARCHITECTURE/IMMICH.md) - it's seeded with real test data
specifically to exercise these queries. Run `docker compose up -d` first.

Tests that touch this app's own tables (games/rounds) run against the same Postgres instance, in
the separate `minigames` schema - that schema is dropped and recreated once per test session
(_reset_own_db below) since this is disposable dev data, not something to preserve.
"""

import pytest
from fastapi.testclient import TestClient

from api.rate_limit import limiter
from main import app
from persistence.base import get_engine, get_session_factory, reset_db
from services.auth_service import AuthService
from services.game_settings import GameSettingsService
from services.games_service import GamesService
from services.immich_service import ImmichService
from services.ml_service import MLService


@pytest.fixture(scope="session")
def engine():
    return get_engine()


@pytest.fixture
def immich_service(engine):
    return ImmichService(engine)


@pytest.fixture
def ml_service(engine):
    return MLService(engine)


@pytest.fixture(scope="session", autouse=True)
def _reset_own_db():
    reset_db(get_engine())


@pytest.fixture
def db_session():
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def games_service(db_session, immich_service, ml_service):
    return GamesService(db_session, immich_service, ml_service)


@pytest.fixture
def auth_service(db_session):
    return AuthService(db_session)


@pytest.fixture
def game_settings_service(db_session):
    return GameSettingsService(db_session)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # The TestClient always calls in as the same client IP, and the limiter's in-memory counters
    # live on the shared `limiter` singleton (not per-TestClient) - reset before each test so one
    # test's auth calls don't eat into another test's rate limit budget.
    limiter.reset()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
