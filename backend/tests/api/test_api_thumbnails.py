import hashlib
from uuid import uuid4

from api.deps import get_immich_service
from main import app


class _FakeImmichService:
    """Stands in for ImmichService in `_proxy_thumbnail` tests - only the two methods the thumbnail
    routes actually call, no real Immich round-trip needed."""

    def __init__(self, content: bytes, content_type: str = "image/jpeg") -> None:
        self._content = content
        self._content_type = content_type

    def get_person_thumbnail(self, person_id):
        return self._content, self._content_type

    def get_asset_thumbnail(self, asset_id, size="preview"):
        return self._content, self._content_type


class TestProxyThumbnailCaching:
    def test_sets_cache_control_and_etag(self, logged_client):
        app.dependency_overrides[get_immich_service] = lambda: _FakeImmichService(b"fake-jpeg-bytes")
        try:
            response = logged_client.get(f"/api/v1/people/{uuid4()}/thumbnail")
        finally:
            del app.dependency_overrides[get_immich_service]

        assert response.status_code == 200
        assert response.content == b"fake-jpeg-bytes"
        assert "max-age=1800" in response.headers["cache-control"]
        assert "stale-while-revalidate=86400" in response.headers["cache-control"]
        assert response.headers["etag"] == hashlib.sha1(b"fake-jpeg-bytes").hexdigest()

    def test_returns_304_on_matching_if_none_match(self, logged_client):
        etag = hashlib.sha1(b"fake-jpeg-bytes").hexdigest()
        app.dependency_overrides[get_immich_service] = lambda: _FakeImmichService(b"fake-jpeg-bytes")
        try:
            response = logged_client.get(
                f"/api/v1/people/{uuid4()}/thumbnail",
                headers={"If-None-Match": etag},
            )
        finally:
            del app.dependency_overrides[get_immich_service]

        assert response.status_code == 304
        assert response.content == b""
        assert response.headers["etag"] == etag

    def test_mismatched_if_none_match_returns_full_body(self, logged_client):
        app.dependency_overrides[get_immich_service] = lambda: _FakeImmichService(b"fake-jpeg-bytes")
        try:
            response = logged_client.get(
                f"/api/v1/people/{uuid4()}/thumbnail",
                headers={"If-None-Match": "stale-etag"},
            )
        finally:
            del app.dependency_overrides[get_immich_service]

        assert response.status_code == 200
        assert response.content == b"fake-jpeg-bytes"


class TestRateLimit:
    def test_person_thumbnail_returns_429_after_the_limit(self, logged_client):
        person_id = uuid4()

        responses = [logged_client.get(f"/api/v1/people/{person_id}/thumbnail") for _ in range(61)]

        assert all(r.status_code == 404 for r in responses[:60])
        assert responses[60].status_code == 429

    def test_asset_thumbnail_returns_429_after_the_limit(self, logged_client):
        asset_id = uuid4()

        responses = [logged_client.get(f"/api/v1/assets/{asset_id}/thumbnail") for _ in range(61)]

        assert all(r.status_code == 404 for r in responses[:60])
        assert responses[60].status_code == 429
