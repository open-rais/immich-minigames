from uuid import uuid4


class TestRateLimit:
    def test_person_thumbnail_returns_429_after_the_limit(self, client):
        person_id = uuid4()

        responses = [client.get(f"/api/v1/people/{person_id}/thumbnail") for _ in range(61)]

        assert all(r.status_code == 404 for r in responses[:60])
        assert responses[60].status_code == 429

    def test_asset_thumbnail_returns_429_after_the_limit(self, client):
        asset_id = uuid4()

        responses = [client.get(f"/api/v1/assets/{asset_id}/thumbnail") for _ in range(61)]

        assert all(r.status_code == 404 for r in responses[:60])
        assert responses[60].status_code == 429
