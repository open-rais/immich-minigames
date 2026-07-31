"""Shared slowapi rate limiter, used across auth and the heavier/public game routes - one
Limiter/one counter store for the whole app (storage_uri from config.py, "memory://" by default).
Imported both by main.py (to wire the middleware/exception handler) and the route modules that
decorate their own endpoints with it.

Keyed by session-or-IP (session_or_ip_key below), not a trusted proxy header: this app assumes
nothing about what's in front of it (bare `docker compose up`, behind Caddy/Nginx/Cloudflare
Tunnel, whatever) - an X-Real-IP-trusting key function would need per-deployment config to stay
correct, and silently under-protect (or over-throttle a shared IP) when that assumption doesn't
hold."""

import time

import jwt
from fastapi import HTTPException, Request
from limits import RateLimitItem, parse
from slowapi import Limiter
from slowapi.util import get_remote_address

from audit import audit
from config import get_settings

_COOKIE_NAME = "access_token"
_JWT_ALGORITHM = "HS256"


def session_or_ip_key(request: Request) -> str:
    """A logged-in request's budget follows its account (so switching networks/IPs mid-session
    doesn't reset it, and several accounts behind one NAT'd IP don't share one); an unauthenticated
    request falls back to the raw socket peer. Decodes the session cookie locally, without a DB
    round-trip - this is a rate-limit *counting* key, not an auth decision (api/auth_middleware.py
    owns that), so a token that's technically been revoked (password changed on another device)
    still counting toward its own account's budget is fine - it's still the same account."""
    token = request.cookies.get(_COOKIE_NAME)
    if token is not None:
        try:
            payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_JWT_ALGORITHM])
            return f"user:{payload['sub']}"
        except (jwt.InvalidTokenError, KeyError):
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=session_or_ip_key, storage_uri=get_settings().rate_limit_storage_uri)

# create_game and play_round both run the same ORDER BY random() asset/person query per call (see
# ImmichService) - play_round via BaseGame.create_next_round when starting the next round.
GAME_ACTION_LIMIT = "30/minute"
# /persons/search - ILIKE + translate() over the full `person` table.
SEARCH_LIMIT = "60/minute"
# Both thumbnail proxies - each also makes a real outbound HTTP call to Immich.
THUMBNAIL_LIMIT = "60/minute"

# slowapi's own @limiter.limit(...) decorator can only key by request
# (session_or_ip_key above - IP or, on /login, always IP since there's no session yet), so it
# can't single out "many attempts against the same email" the way credential stuffing actually
# looks: an attacker spreading guesses across IPs (or many victims sharing one IP/NAT) both defeat
# an IP-only limit. This reuses the exact same Limiter's underlying storage/strategy (limiter.
# limiter, a limits.strategies.FixedWindowRateLimiter) with an explicit email-derived key instead -
# called from inside the login handler itself (api/auth_api.py), since slowapi's decorator has no
# access to the parsed request body to key by. The route's own @limiter.limit(...) IP-based
# decorator stays too, as a loose global cap independent of this.
_LOGIN_EMAIL_LIMIT: RateLimitItem = parse("5/minute")


def enforce_login_email_limit(email: str, path: str) -> None:
    """Raises HTTPException(429) once this email has attempted to log in 5 times in the last
    minute, successful or not - every attempt counts, not just wrong-password ones, since the
    thing being bounded is guessing attempts against one account, and a correct guess is still a
    guess. Call before checking the password, so a 429 never depends on whether the password
    happened to be right."""
    if limiter.limiter.hit(_LOGIN_EMAIL_LIMIT, "login-email", email):
        return
    stats = limiter.limiter.get_window_stats(_LOGIN_EMAIL_LIMIT, "login-email", email)
    retry_after = max(0, int(stats.reset_time - time.time()))
    audit("rate_limited", path=path, scope="login_email", key=email)
    raise HTTPException(
        status_code=429,
        detail="too many login attempts for this email - try again later",
        headers={"Retry-After": str(retry_after)},
    )
