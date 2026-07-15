"""App entrypoint. Mounts the API router and maps this app's domain exceptions to HTTP responses
in one place (routes just let them propagate - see api/api.py).

Own-schema DB tables are no longer created here - schema is Alembic-owned (see backend/alembic/):
the packaged Docker image runs `alembic upgrade head` in docker-entrypoint.sh before starting this
app, and bare `uv run uvicorn` dev usage expects that same command to have been run manually once
(see README.md's Development Setup). persistence/base.py's init_db/reset_db still exist for
tests (tests/conftest.py's reset_db against the throwaway test DB), unrelated to Alembic."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.api import router
from api.rate_limit import limiter
from games.immichdle import DuplicateGuessError, InvalidGuessError
from games.whos_that_person import IncompleteGuessError
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

app = FastAPI(title="Immich Minigames")
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
