"""
These are integration tests against the real dev Immich Postgres brought up by
docker-compose.yml (see docs/ARCHITECTURE/IMMICH.md) - it's seeded with real test data
specifically to exercise these queries. Run `docker compose up -d` first.

Tests that touch this app's own tables (games/rounds) run against this app's OWN database on that
same Postgres instance - a different database from Immich's, hence the two engine fixtures below.
Its tables are dropped and recreated once per test session (_reset_own_db) since this is
disposable dev data, not something to preserve.

That database has to exist before any of this works. Provision it once with:
    docker compose -f docker-compose.app.yml run --rm db-init
"""

import pytest
from fastapi.testclient import TestClient

from api.rate_limit import limiter
from main import app
from persistence.base import get_app_engine, get_session_factory, reset_db
from persistence.immich_db import get_immich_engine
from services.auth_service import AuthService
from services.game_settings import GameSettingsService
from services.games_service import GamesService
from services.immich_service import ImmichService
from services.ml_service import MLService


@pytest.fixture(scope="session")
def immich_engine():
    return get_immich_engine()


@pytest.fixture(scope="session")
def app_engine():
    return get_app_engine()


@pytest.fixture
def immich_service(immich_engine):
    return ImmichService(immich_engine)


@pytest.fixture
def ml_service(immich_engine):
    return MLService(immich_engine)


@pytest.fixture(scope="session", autouse=True)
def _reset_own_db():
    reset_db(get_app_engine())


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
