"""Shared slowapi rate limiter, used across auth and the heavier/public game routes - keyed by
client IP, in-memory storage (no Redis in this stack yet, and a single-process deployment doesn't
need one). Imported both by main.py (to wire the middleware/exception handler) and the route
modules that decorate their own endpoints with it, so there's exactly one Limiter/one counter store
for the whole app."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_client_ip(request: Request) -> str:
    """Real client IP behind nginx. nginx sets X-Real-IP from its own $remote_addr
    (frontend/nginx.conf.template) - trustworthy here because docker-compose.app.yml never
    publishes the backend's port, so nothing external can reach it directly to forge the header.
    Falls back to the raw socket peer for dev, where there's no nginx in front and the header is
    simply absent."""
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)

# create_game and play_round both run the same ORDER BY random() asset/person query per call (see
# ImmichService) - play_round via BaseGame.create_next_round when starting the next round.
GAME_ACTION_LIMIT = "30/minute"
# /persons/search - ILIKE + translate() over the full `person` table.
SEARCH_LIMIT = "60/minute"
# Both thumbnail proxies - each also makes a real outbound HTTP call to Immich.
THUMBNAIL_LIMIT = "60/minute"
