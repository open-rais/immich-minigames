import pytest


class TestSearchPersons:
    def test_single_letter_query_returns_id_and_name_only(self, client):
        response = client.get("/api/v1/persons/search", params={"query": "a", "limit": 50})

        assert response.status_code == 200
        body = response.json()
        assert body["results"]
        for result in body["results"]:
            assert set(result.keys()) == {"id", "name"}

    def test_default_limit_is_three(self, client, immich_service):
        matches = immich_service.search_persons("a", limit=100)
        if len(matches) < 3:
            pytest.skip("dev data needs at least 3 people matching 'a' for this test")

        response = client.get("/api/v1/persons/search", params={"query": "a"})

        assert len(response.json()["results"]) == 3

    def test_offset_pages_through_results(self, client, immich_service):
        matches = immich_service.search_persons("a", limit=100)
        if len(matches) < 4:
            pytest.skip("dev data needs at least 4 people matching 'a' for this test")

        first_page = client.get("/api/v1/persons/search", params={"query": "a", "offset": 0, "limit": 2}).json()
        second_page = client.get("/api/v1/persons/search", params={"query": "a", "offset": 2, "limit": 2}).json()

        first_ids = {r["id"] for r in first_page["results"]}
        second_ids = {r["id"] for r in second_page["results"]}
        assert first_ids.isdisjoint(second_ids)

    def test_missing_query_returns_422(self, client):
        response = client.get("/api/v1/persons/search")

        assert response.status_code == 422

    def test_empty_query_returns_422(self, client):
        response = client.get("/api/v1/persons/search", params={"query": ""})

        assert response.status_code == 422


class TestRateLimit:
    def test_returns_429_after_the_limit(self, client):
        responses = [client.get("/api/v1/persons/search", params={"query": "a"}) for _ in range(61)]

        assert all(r.status_code == 200 for r in responses[:60])
        assert responses[60].status_code == 429
