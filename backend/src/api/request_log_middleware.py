"""Access log (docs/TODO/LOGGING.md §4.3, phase F1) - replaces uvicorn's own access log (disabled
in logging_setup.py) with one that knows the request's user. Registered as the outermost
middleware (last `add_middleware` call in main.py - Starlette wraps in reverse registration order,
same reasoning as AuthMiddleware's own comment there) so it also measures/logs the 401s
AuthMiddleware cuts before they reach a route, and can catch an unhandled exception on its way
out to ServerErrorMiddleware (which sits outside every `add_middleware`-registered middleware and
would otherwise send the 500 with nothing of ours ever logging it).
"""

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from api.request_context import forwarded_for_var, ip_var, request_id_var

_access_logger = logging.getLogger("access")


def _path_with_query(request: Request) -> str:
    # Query included (decision in §4.3): no endpoint today puts a secret in a query string - reset
    # tokens/invitation codes travel in the request body, not the URL.
    if request.url.query:
        return f"{request.url.path}?{request.url.query}"
    return request.url.path


def _identity_fields(request: Request) -> dict[str, object]:
    # request.state.user_id/username, not request.state.user.id/.username: AuthMiddleware's own
    # session is already closed by the time call_next returns here (its `finally` runs first,
    # innermost-out), and if the route committed anything in between, SQLAlchemy's expire-on-commit
    # would turn `.id`/`.username` into a lazy reload that DetachedInstanceErrors on a closed
    # session - see auth_middleware.py's comment where these scalars are captured.
    #
    # Also why request.state at all, not the user contextvar: AuthMiddleware sits inside this
    # middleware, so a value it sets in its own task never propagates back up to us once call_next
    # returns (api/request_context.py's own docstring).
    fields: dict[str, object] = {}
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        fields["user_id"] = user_id
        fields["username"] = request.state.username
    auth_fail = getattr(request.state, "auth_fail", None)
    if auth_fail is not None:
        fields["auth_fail"] = auth_fail
    return fields


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        request_id_token = request_id_var.set(request_id)
        ip_token = ip_var.set(request.client.host if request.client else None)
        forwarded_for_token = forwarded_for_var.set(request.headers.get("x-forwarded-for"))

        start = time.monotonic()
        try:
            try:
                response = await call_next(request)
            except Exception:
                # request_id/ip/forwarded_for come from the contextvars themselves (still bound
                # here, reset only in `finally` below) - JsonFormatter/ConsoleFormatter merge those
                # into every record (logging_setup.py), so only what they can't see goes in extra.
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                _access_logger.exception(
                    "unhandled exception",
                    extra={
                        "method": request.method,
                        "path": _path_with_query(request),
                        "status": 500,
                        "duration_ms": duration_ms,
                        **_identity_fields(request),
                    },
                )
                raise

            duration_ms = round((time.monotonic() - start) * 1000, 2)
            response.headers["X-Request-Id"] = request_id
            _access_logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": _path_with_query(request),
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    **_identity_fields(request),
                },
            )
            return response
        finally:
            request_id_var.reset(request_id_token)
            ip_var.reset(ip_token)
            forwarded_for_var.reset(forwarded_for_token)
