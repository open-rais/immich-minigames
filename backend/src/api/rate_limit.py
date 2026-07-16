"""Shared slowapi rate limiter for the auth endpoints (see AUDIT_TODO.md #1) - keyed by client IP,
in-memory storage (no Redis in this stack yet, and a single-process deployment doesn't need one).
Imported both by main.py (to wire the middleware/exception handler) and api/auth_api.py (to
decorate the actual routes) so there's exactly one Limiter/one counter store for the whole app."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
