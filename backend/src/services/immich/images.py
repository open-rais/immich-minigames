"""Image bytes via Immich's REST API - never Postgres, see the package docstring's "Dos formas de
hablar con Immich"."""

from functools import lru_cache
from uuid import UUID

import httpx

from config import Settings


# Reused across requests (pooled connections, one client) instead of opening a new connection per
# thumbnail. A bounded timeout means a slow/hung Immich never blocks a worker thread indefinitely.
@lru_cache(maxsize=1)
def _get_http_client() -> httpx.Client:
    return httpx.Client(timeout=10.0)


def get_asset_thumbnail(settings: Settings, asset_id: UUID, size: str = "preview") -> tuple[bytes, str]:
    """Fetches an asset's image bytes via Immich's REST API. `size="preview"` (~1440px JPEG
    derivative) rather than the default `thumbnail` (~250px, too small for fullscreen) or
    `original` (may be HEIC/RAW/video, not safely renderable in a browser <img>).

    Raises httpx.HTTPStatusError (e.g. 404 - no thumbnail, 401 - bad IMMICH_API_KEY) or
    httpx.RequestError (Immich unreachable/timed out) - see api/api.py for how each maps to a
    response."""
    response = _get_http_client().get(
        f"{settings.immich_server_url}/api/assets/{asset_id}/thumbnail",
        params={"size": size},
        headers={"x-api-key": settings.immich_api_key},
    )
    response.raise_for_status()
    return response.content, response.headers.get("content-type", "image/jpeg")


def get_person_thumbnail(settings: Settings, person_id: UUID) -> tuple[bytes, str]:
    """Fetches a person's face thumbnail via Immich's REST API. Returns (image bytes, content-type).

    Raises httpx.HTTPStatusError (e.g. 404 - no thumbnail, 401 - bad IMMICH_API_KEY) or
    httpx.RequestError (Immich unreachable/timed out) - see api/api.py for how each maps to a
    response."""
    response = _get_http_client().get(
        f"{settings.immich_server_url}/api/people/{person_id}/thumbnail",
        headers={"x-api-key": settings.immich_api_key},
    )
    response.raise_for_status()
    return response.content, response.headers.get("content-type", "image/jpeg")
