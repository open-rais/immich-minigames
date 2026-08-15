"""App entrypoint. Mounts the API router and maps this app's domain exceptions to HTTP responses
in one place (routes just let them propagate - see api/api.py).

Schema is Alembic-owned (see backend/alembic/):
the packaged Docker image runs `alembic upgrade head` in docker-entrypoint.sh before starting this
app, and bare `uv run uvicorn` dev usage expects that same command to have been run manually once
(see README.md's Development Setup). persistence/base.py's init_db/reset_db still exist for
tests (tests/conftest.py's reset_db against the throwaway test DB), unrelated to Alembic."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.api import router
from api.auth_middleware import AuthMiddleware
from api.deps import get_embedding_job_runner
from api.error_handlers import register_error_handlers
from api.rate_limit import limiter, session_or_ip_key
from api.request_log_middleware import RequestLogMiddleware
from audit import audit
from config import get_settings
from logging_setup import configure_logging
from persistence.base import get_session_factory
from services.admin_bootstrap import ensure_admin


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Idempotent (see services/admin_bootstrap.py), so it's safe to run on every startup - dev's
    # --reload included, and the packaged image's docker-entrypoint.sh (after `alembic upgrade
    # head`, migration 0003 adds the column this depends on).
    session = get_session_factory()()
    try:
        ensure_admin(session, get_settings())
    finally:
        session.close()
    yield
    # A running embedding job's thread is daemon (it wouldn't block process exit on its own), but
    # cancelling and joining here first gives an in-flight entity a chance to finish its write
    # instead of being cut off mid-upsert by the process disappearing under it.
    get_embedding_job_runner().shutdown()


configure_logging(get_settings())

app = FastAPI(title="Immich Minigames", lifespan=_lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
# Added after SlowAPIMiddleware so it's the outermost layer (Starlette wraps in reverse
# registration order) - an unauthenticated request to a protected route 401s immediately without
# touching rate-limit state at all, rather than being rate-limited on its way to a 401 anyway.
app.add_middleware(AuthMiddleware)
# Added last so it's the outermost of all (same reverse-registration-order reasoning as above) -
# it measures/logs the 401s AuthMiddleware cuts too, not just what makes it past it.
app.add_middleware(RequestLogMiddleware)


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    audit("rate_limited", path=request.url.path, scope="route", key=session_or_ip_key(request))
    response = JSONResponse(status_code=429, content={"detail": f"rate limit exceeded: {exc.detail}"})
    return limiter._inject_headers(response, request.state.view_rate_limit)


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
register_error_handlers(app)

app.include_router(router)
