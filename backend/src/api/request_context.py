"""Per-request contextvars (docs/TODO/LOGGING.md §4.2, phase F1) - what every log record should
carry without call sites threading it through manually. `RequestLogMiddleware` (the outermost
middleware) sets `request_id`/`ip`/`forwarded_for` before calling down into the app, and
`AuthMiddleware` sets `user` once it resolves the session cookie - `logging_setup.py`'s formatters
merge `context_fields()` into every record they format.

Contextvars set here propagate downward (a middleware's `call_next` runs in a task that inherits a
copy of the calling context), but NOT back up through `BaseHTTPMiddleware` once that inner task
returns - so `user`, set by `AuthMiddleware` which is *inside* `RequestLogMiddleware`, is never
visible to the access log record the outer middleware emits after `call_next` returns. That log
line reads the user from `request.state` instead (shared via the ASGI scope across middlewares,
unlike contextvars) - see `api/request_log_middleware.py`.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
ip_var: ContextVar[str | None] = ContextVar("ip", default=None)
forwarded_for_var: ContextVar[str | None] = ContextVar("forwarded_for", default=None)
user_var: ContextVar[dict[str, str] | None] = ContextVar("user", default=None)


def context_fields() -> dict[str, object]:
    """Snapshot of whatever context vars are currently set, for a formatter to merge into a log
    record - only keys that are actually set, so logging done outside a request (startup, a
    background task) doesn't grow null fields."""
    fields: dict[str, object] = {}
    if (request_id := request_id_var.get()) is not None:
        fields["request_id"] = request_id
    if (ip := ip_var.get()) is not None:
        fields["ip"] = ip
    if (forwarded_for := forwarded_for_var.get()) is not None:
        fields["forwarded_for"] = forwarded_for
    if (user := user_var.get()) is not None:
        fields["user_id"] = user["id"]
        fields["username"] = user["username"]
    return fields
