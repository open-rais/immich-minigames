"""Structural coverage for api/auth_middleware.py (roadmap #H, F3) - walks every route actually
registered on the app and asserts each one outside the allow-list 401s without a cookie, so a
route added tomorrow and never wired up for auth is covered by construction rather than by someone
remembering to add a test for it."""

import re
from collections.abc import Iterator

from main import app

_ALLOW_LIST = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/logout",
    }
)
_DUMMY_ID = "00000000-0000-0000-0000-000000000000"
_PARAM_PATTERN = re.compile(r"\{[^}]+\}")


def _iter_routes(routes) -> Iterator[tuple[str, set[str]]]:
    """This FastAPI version wraps every include_router() call in an internal `_IncludedRouter`
    holding the real sub-APIRouter on `.original_router` instead of flattening its routes onto the
    parent - app.routes alone only ever shows 4 top-level entries (the auto docs routes) plus one
    `_IncludedRouter` per include_router() call in api/api.py, recursively (admin/auth/daily
    routers are themselves included from within api.router). Walk through that structure to reach
    the concrete (path, methods) pairs."""
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            yield from _iter_routes(route.original_router.routes)
            continue
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is not None and methods:
            yield path, methods


def _concrete_paths(route_path: str) -> list[str]:
    concrete = _PARAM_PATTERN.sub(_DUMMY_ID, route_path)
    # Both the plain path and a trailing-slash variant - the middleware's allow-list check happens
    # before Starlette's own routing (and its redirect_slashes) runs, so a trailing slash must not
    # slip an otherwise-protected (or otherwise-allow-listed) path past the check unnoticed.
    return [concrete, f"{concrete}/"]


def test_every_registered_route_outside_the_allow_list_requires_a_cookie(client):
    client.cookies.clear()
    checked = 0
    for path, methods in _iter_routes(app.routes):
        if path in _ALLOW_LIST:
            continue
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            for concrete_path in _concrete_paths(path):
                response = client.request(method, concrete_path)
                assert response.status_code == 401, (
                    f"{method} {concrete_path} did not 401 without a cookie (got {response.status_code})"
                )
                checked += 1
    # Sanity net: fails loudly if app.routes ever came back empty/near-empty instead of silently
    # passing a no-op test.
    assert checked > 40


def test_allow_listed_routes_do_not_require_a_cookie(client):
    client.cookies.clear()
    # Wrong credentials, not a real login - just confirms the route itself is reachable without a
    # cookie (401 for "bad password", not for "no session").
    response = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid email or password"


def test_docs_and_openapi_require_a_cookie(client):
    client.cookies.clear()
    assert client.get("/docs").status_code == 401
    assert client.get("/redoc").status_code == 401
    assert client.get("/openapi.json").status_code == 401
