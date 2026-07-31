"""Shared FastAPI dependencies used by more than one router (api/api.py, api/auth_api.py,
api/daily_api.py)."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from persistence.base import get_session_factory
from persistence.games_repository import GameRepository
from services.daily_challenge_service import DailyChallengeService
from services.daily_games_service import DailyGamesService
from services.daily_settings import DailySettingsService
from services.game_factory import GameFactory
from services.game_settings_service import GameSettingsService
from services.games_service import GamesService
from services.immich_service import ImmichService
from services.invite_service import InviteService
from services.ml_service import MLService
from services.scores_service import ScoresService

_session_factory = get_session_factory()


def get_db_session(request: Request) -> Iterator[Session]:
    # Roadmap #H, F3 - api/auth_middleware.py resolves request.state.user via its own session
    # *before* routing even happens, and stashes that same session on request.state.db_session.
    # Reusing it here (rather than opening a second one) isn't just an optimization: state.user is
    # a UserModel loaded on that session, and a route that mutates it (e.g. change_password) needs
    # it attached to the *same* session it calls session.commit() on, or the mutation is silently
    # lost on a detached object nothing ever flushes. The middleware owns closing this one (after
    # the whole request finishes, in its own finally) - only open+close a fresh session here for
    # the few allow-listed routes the middleware never touches at all (login/register/etc).
    existing = getattr(request.state, "db_session", None)
    if existing is not None:
        yield existing
        return

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


# Roadmap #H, F1/F2 - moved here (from api/admin_invites_api.py, where it started) so
# api/admin_api.py can also depend on it (the new password-reset endpoint, F2) without
# admin_api.py <-> admin_invites_api.py becoming a circular import (admin_invites_api.py already
# imports get_current_admin_user *from* admin_api.py).
def get_invite_service(session: Annotated[Session, Depends(get_db_session)]) -> InviteService:
    return InviteService(session)


def get_game_repository(session: Annotated[Session, Depends(get_db_session)]) -> GameRepository:
    return GameRepository(session)


def get_game_factory(
    session: Annotated[Session, Depends(get_db_session)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
    ml_service: Annotated[MLService, Depends(get_ml_service)],
) -> GameFactory:
    return GameFactory(session, immich_service, ml_service, GameSettingsService(session))


# Roadmap #G - moved here (rather than staying private to api/api.py, as it originally was) so
# api/daily_api.py can also depend on it without api.py <-> daily_api.py becoming a circular import
# (api.py already imports daily_api.py's router to mount it).
def get_games_service(
    repository: Annotated[GameRepository, Depends(get_game_repository)],
    factory: Annotated[GameFactory, Depends(get_game_factory)],
) -> GamesService:
    return GamesService(repository, factory)


def get_daily_games_service(
    session: Annotated[Session, Depends(get_db_session)],
    repository: Annotated[GameRepository, Depends(get_game_repository)],
    factory: Annotated[GameFactory, Depends(get_game_factory)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> DailyGamesService:
    return DailyGamesService(
        repository, factory, DailySettingsService(session), DailyChallengeService(session, immich_service)
    )


def get_scores_service(repository: Annotated[GameRepository, Depends(get_game_repository)]) -> ScoresService:
    return ScoresService(repository)
