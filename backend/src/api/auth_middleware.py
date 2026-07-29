"""Default-deny session middleware (roadmap #H, F3 - "el corte") - every request needs a valid
session cookie except an exact allow-list of public auth endpoints. A middleware, not a
per-router dependency: a route someone adds tomorrow and forgets to protect is covered by
construction (it breaks closed), where a dependency-based approach would leave it wide open by
default. See tests/test_auth_middleware.py for the structural test that keeps this true."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from api.request_context import user_var
from persistence.base import get_session_factory
from services.auth_service import AuthService, UnauthorizedError

_COOKIE_NAME = "access_token"

# Exact paths, not prefixes (docs/TODO/NEW-AUTH.md §4.2) - logout is included so a session that's
# already invalid can still "log out" client-side instead of getting stuck.
_ALLOW_LIST = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/logout",
    }
)


def _normalize(path: str) -> str:
    # Strips a single trailing slash so /login and /login/ are treated the same - the allow-list
    # check happens before Starlette's own routing (and its redirect_slashes) ever runs, so without
    # this a trailing-slash variant of an allow-listed path would be wrongly rejected.
    return path[:-1] if len(path) > 1 and path.endswith("/") else path


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": detail})


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _normalize(request.url.path) in _ALLOW_LIST:
            return await call_next(request)

        token = request.cookies.get(_COOKIE_NAME)
        if token is None:
            # Decision [G] (docs/TODO/LOGGING.md): not an audit event on its own (an expired
            # cookie in a stale tab 401s in bursts, pure noise) - the access log's `auth_fail`
            # field is what lets an analysis tell "session expired" apart from "token tampered
            # with" after the fact.
            request.state.auth_fail = "missing_cookie"
            return _unauthorized("not authenticated")

        # One session for the whole request, not just this validation step - api/deps.py's
        # get_db_session reuses this exact session (via request.state.db_session) instead of
        # opening a second one, so request.state.user below stays attached to whatever session a
        # route's own dependencies (AuthService, GamesService, ...) go on to use. Without that, a
        # route mutating the user (e.g. change_password) would be mutating a detached object on an
        # already-closed session - the change is silently never flushed anywhere.
        session = get_session_factory()()
        request.state.db_session = session
        try:
            # Reused as-is, not reimplemented - already has the iat vs password_changed_at
            # revocation check (roadmap #H, F0), so that logic exists in exactly one place.
            user = AuthService(session).get_user_from_token(token)
        except UnauthorizedError as exc:
            session.close()
            request.state.auth_fail = str(exc)
            return _unauthorized(str(exc))

        request.state.user = user
        # Scalars captured now, not read back off `user` later: RequestLogMiddleware (outermost,
        # docs/TODO/LOGGING.md §4.3) logs the access record only after call_next returns here -
        # by then this method's own `finally` has already closed `session`, and if the route did
        # any commit in between (e.g. change_password), SQLAlchemy's default expire-on-commit
        # makes `user.id`/`user.username` a lazy reload that DetachedInstanceErrors on a closed
        # session. Plain strings on request.state have no such lifecycle.
        request.state.user_id = str(user.id)
        request.state.username = user.username
        # Downstream app logging (docs/TODO/LOGGING.md §4.2) - the outer access log middleware
        # reads request.state instead (see its own module docstring for why this contextvar isn't
        # visible to it).
        user_token = user_var.set({"id": request.state.user_id, "username": request.state.username})
        try:
            return await call_next(request)
        finally:
            user_var.reset(user_token)
            session.close()
