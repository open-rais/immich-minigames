"""Maps this app's domain exceptions to HTTP status codes, one row per exception type - main.py
registers these on the FastAPI app via register_error_handlers(). Every entry here shares the same
response shape (`_error_handler`'s `{"detail": str(exc)}`); RateLimitExceeded doesn't (it audits
and injects rate-limit headers), so it stays a handler of its own in main.py rather than a row in
this table."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from games.immichdle import DuplicateGuessError, InvalidGuessError
from games.whos_that_person import IncompleteGuessError
from services.auth_service import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UnauthorizedError,
    UsernameAlreadyExistsError,
)
from services.embedding_jobs import JobAlreadyRunningError
from services.errors import (
    DailyAlreadyPlayedError,
    DailyNotEnabledError,
    GameNotFoundError,
    GameOwnershipError,
    NotEnoughContentError,
    RoundNotPendingError,
    UnsupportedGameError,
)
from services.game_settings_service import InvalidGameSettingValueError, UnknownGameSettingError
from services.invite_service import InvalidInviteError, InviteNotFoundError
from services.notifications import NoPushSubscriptionsError, PushSendFailedError
from services.notifications.endpoint_safety import PushEndpointRejectedError
from services.notifications.sender import PushNotConfiguredError
from services.reports_service import InvalidReportReasonError, ReportNotFoundError

EXCEPTION_STATUS: dict[type[Exception], int] = {
    UnsupportedGameError: 400,
    NotEnoughContentError: 422,
    DuplicateGuessError: 400,
    InvalidGuessError: 400,
    IncompleteGuessError: 422,
    GameOwnershipError: 403,
    GameNotFoundError: 404,
    RoundNotPendingError: 409,
    InvalidCredentialsError: 401,
    UnauthorizedError: 401,
    EmailAlreadyExistsError: 409,
    UsernameAlreadyExistsError: 409,
    UnknownGameSettingError: 400,
    InvalidGameSettingValueError: 400,
    DailyNotEnabledError: 404,
    DailyAlreadyPlayedError: 409,
    InvalidInviteError: 400,
    InviteNotFoundError: 404,
    JobAlreadyRunningError: 409,
    ReportNotFoundError: 404,
    InvalidReportReasonError: 400,
    PushEndpointRejectedError: 400,
    PushNotConfiguredError: 503,
    NoPushSubscriptionsError: 404,
    PushSendFailedError: 502,
}


def _error_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def register_error_handlers(app: FastAPI) -> None:
    for exception_type, status_code in EXCEPTION_STATUS.items():
        app.add_exception_handler(exception_type, _error_handler(status_code))
