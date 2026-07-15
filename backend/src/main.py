"""App entrypoint. Initializes the own-schema DB tables, mounts the API router, and maps this
app's domain exceptions to HTTP responses in one place (routes just let them propagate - see
api/api.py)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.api import router
from api.rate_limit import limiter
from games.immichdle import DuplicateGuessError, InvalidGuessError
from games.whos_that_person import IncompleteGuessError
from persistence.base import init_db
from services.auth_service import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UnauthorizedError,
    UsernameAlreadyExistsError,
)
from services.games_service import (
    GameNotFoundError,
    GameOwnershipError,
    RoundNotPendingError,
    UnsupportedGameError,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Immich Minigames", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


def _error_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(status_code=429, content={"detail": f"rate limit exceeded: {exc.detail}"})
    return limiter._inject_headers(response, request.state.view_rate_limit)


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_exception_handler(UnsupportedGameError, _error_handler(400))
app.add_exception_handler(DuplicateGuessError, _error_handler(400))
app.add_exception_handler(InvalidGuessError, _error_handler(400))
app.add_exception_handler(IncompleteGuessError, _error_handler(422))
app.add_exception_handler(GameOwnershipError, _error_handler(403))
app.add_exception_handler(GameNotFoundError, _error_handler(404))
app.add_exception_handler(RoundNotPendingError, _error_handler(409))
app.add_exception_handler(InvalidCredentialsError, _error_handler(401))
app.add_exception_handler(UnauthorizedError, _error_handler(401))
app.add_exception_handler(EmailAlreadyExistsError, _error_handler(409))
app.add_exception_handler(UsernameAlreadyExistsError, _error_handler(409))

app.include_router(router)
