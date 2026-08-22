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

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.rate_limit import limiter
from api.request_context import context_fields
from config import get_settings
from main import app
from persistence.base import get_app_engine, get_session_factory, reset_db
from persistence.games_repository import GameRepository
from persistence.immich_db import get_immich_engine
from persistence.users import UserModel
from services.auth_service import AuthService
from services.daily_challenge_service import DailyChallengeService
from services.daily_games_service import DailyGamesService
from services.daily_settings import DailySettingsService
from services.game_factory import GameFactory
from services.game_settings_service import GameSettingsService
from services.games_service import GamesService
from services.immich import ImmichService
from services.invite_service import InviteService
from services.ml_service import MLService
from services.reports_service import ReportsService
from services.scores_service import ScoresService


class _LogCapture(logging.Handler):
    """Captures records directly off a logger, bypassing caplog - `audit`/`access` both set
    propagate=False (logging_setup.py), so records emitted on them never reach
    caplog's root-attached handler. Also snapshots api.request_context.context_fields() at the same
    point emit() runs (still inside the request's own task/context, unlike by the time a test
    asserts afterward) - a raw record's own __dict__ only has whatever a call site explicitly put in
    `extra`; request_id/ip/user_id/username are merged in later, at *format* time, by
    JsonFormatter/ConsoleFormatter (logging_setup.py) - a formatter-less capture handler like this
    one never sees them any other way."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.contexts: list[dict[str, object]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        self.contexts.append(context_fields())

    def clear(self) -> None:
        # Clears both lists together - `records` and `contexts` are index-aligned (emit() appends
        # to both atomically), so clearing only one desyncs a later `contexts[i]` from `records[i]`.
        self.records.clear()
        self.contexts.clear()


def _capture_logger(name: str):
    handler = _LogCapture()
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


@pytest.fixture
def access_log():
    yield from _capture_logger("access")


@pytest.fixture
def audit_log():
    yield from _capture_logger("audit")


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


# Fixed, not randomized like every other test account (`_register`/`logged_client` suffix a fresh
# uuid onto every email/username so parallel tests never collide) - this one is deliberately the
# same every pytest run, so there's always a known (email, password) to log into the dev stack's
# frontend as an admin with afterward, instead of having to go dig a specific test's random account
# out of the DB.
FIXED_ADMIN_EMAIL = "admin@example.com"
FIXED_ADMIN_USERNAME = "admin"
FIXED_ADMIN_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(scope="session", autouse=True)
def _seed_fixed_admin(_reset_own_db):
    """Depends on _reset_own_db (not just autouse ordering) to guarantee this is the very first
    registration of the session - AuthService's bootstrap branch (the only one that doesn't need a
    real invite) only applies to the very first account in an empty `users` table. Opens its own
    throwaway session and commits immediately, same technique as mint_invite_code() below (the
    function-scoped `db_session` fixture isn't available at session scope)."""
    session = get_session_factory()()
    try:
        user = AuthService(session).register(
            email=FIXED_ADMIN_EMAIL,
            username=FIXED_ADMIN_USERNAME,
            full_name="Admin",
            password=FIXED_ADMIN_PASSWORD,
            invite_code=mint_invite_code(),
        )
        user.is_admin = True
        session.commit()
    finally:
        session.close()


@pytest.fixture
def db_session():
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def game_repository(db_session):
    return GameRepository(db_session)


@pytest.fixture
def game_factory(db_session, immich_service, ml_service, game_settings_service):
    return GameFactory(db_session, immich_service, ml_service, game_settings_service)


@pytest.fixture
def games_service(game_repository, game_factory):
    return GamesService(game_repository, game_factory)


@pytest.fixture
def auth_service(db_session):
    return AuthService(db_session)


@pytest.fixture
def game_settings_service(db_session):
    return GameSettingsService(db_session)


@pytest.fixture
def daily_settings_service(db_session):
    return DailySettingsService(db_session)


@pytest.fixture
def daily_challenge_service(db_session, immich_service):
    return DailyChallengeService(db_session, immich_service)


@pytest.fixture
def daily_games_service(game_repository, game_factory, daily_settings_service, daily_challenge_service):
    return DailyGamesService(game_repository, game_factory, daily_settings_service, daily_challenge_service)


@pytest.fixture
def scores_service(game_repository):
    return ScoresService(game_repository)


@pytest.fixture
def reports_service(db_session):
    return ReportsService(db_session)


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


@pytest.fixture
def logged_client(client):
    """The default-deny middleware (api/auth_middleware.py) rejects every
    request without a valid session cookie, so any test hitting a real endpoint (not calling a
    service directly) needs one. Registers a disposable throwaway account and returns the same `client`,
    now carrying its session cookie."""
    unique = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"logged-{unique}@example.com",
            "username": f"logged-{unique}",
            "full_name": "Logged In User",
            "password": "correct-horse-battery-staple",
            "invite_code": mint_invite_code(),
        },
    )
    assert response.status_code == 201
    return client


def mint_invite_code(kind: str = "invite") -> str:
    """Registration requires a valid invite_code (except for the very first
    account). A plain function, not a fixture: every test file's own `_register()` helper stays a
    plain function too, and this lets it mint a real, valid invite with a one-line change to its
    default body dict rather than threading an invite_service fixture through every one of the
    ~70 existing `_register(client, ...)` call sites across the suite. Opens its own throwaway
    session (not the `db_session` fixture, which isn't available outside a test/fixture function)
    and commits immediately (InviteService.create_invite always does) so the token is visible to
    the `client` fixture's own, separate request-scoped session right after.

    Bootstrap-aware: if `users` is currently empty, the *next* registration hits AuthService's
    bootstrap branch, which never checks the `invites` table at all - it only
    accepts INITIAL_INVITE_TOKEN (or, if that's unset, anything). A freshly-minted real invite
    would be silently ignored there, which is harmless when INITIAL_INVITE_TOKEN is unset, but
    wrong when a developer's own .env has it set (as this one does) - so return that value
    instead in exactly that case."""
    session = get_session_factory()()
    try:
        if kind == "invite" and session.scalar(select(UserModel.id).limit(1)) is None:
            token = get_settings().initial_invite_token
            if token is not None:
                return token
        return InviteService(session).create_invite(kind=kind)[1]
    finally:
        session.close()
