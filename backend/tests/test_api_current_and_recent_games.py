"""Route-level coverage for the current/recent-games endpoints - GamesService-level behavior (the
abandon side effect, the scoping/filtering rules) is already covered by test_games_service.py; this
file only checks the HTTP-layer conventions (status codes, auth requirements, response shape)."""

from uuid import uuid4

from conftest import mint_invite_code


def _create_game(client, *, mode: str = "personAssets") -> dict:
    response = client.post("/api/v1/games", json={"type": "more-or-less", "mode": mode})
    assert response.status_code == 201
    return response.json()


def _register(client) -> None:
    unique = uuid4().hex[:8]
    body = {
        "email": f"user-{unique}@example.com",
        "username": f"user-{unique}",
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
        "invite_code": mint_invite_code(),
    }
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201


class TestGetCurrentGame:
    def test_without_a_cookie_returns_401(self, client):
        client.cookies.clear()

        response = client.get("/api/v1/games/current", params={"game_type": "more-or-less", "mode": "personAssets"})

        assert response.status_code == 401

    def test_returns_null_when_nothing_active(self, logged_client):
        response = logged_client.get(
            "/api/v1/games/current", params={"game_type": "more-or-less", "mode": "personAssets"}
        )

        assert response.status_code == 200
        assert response.json() == {"game": None}

    def test_returns_the_active_game(self, logged_client):
        game = _create_game(logged_client)

        response = logged_client.get(
            "/api/v1/games/current", params={"game_type": "more-or-less", "mode": "personAssets"}
        )

        assert response.status_code == 200
        assert response.json()["game"]["id"] == game["id"]

    def test_unsupported_mode_returns_400(self, logged_client):
        response = logged_client.get(
            "/api/v1/games/current", params={"game_type": "geoguessr", "mode": "not-a-real-mode"}
        )

        assert response.status_code == 400

    def test_starting_a_new_game_of_the_same_mode_abandons_the_old_one(self, logged_client):
        first = _create_game(logged_client)
        _create_game(logged_client)

        response = logged_client.get(
            "/api/v1/games/current", params={"game_type": "more-or-less", "mode": "personAssets"}
        )

        assert response.json()["game"]["id"] != first["id"]


class TestGetRecentGames:
    def test_requires_login(self, client):
        client.cookies.clear()

        response = client.get("/api/v1/games/recent")

        assert response.status_code == 401

    def test_returns_at_most_five_games(self, client):
        _register(client)
        # Each create_game call for the same mode abandons the previous one (see
        # test_games_service.py's TestCreateGameAbandonsPreviousActiveGame), so 7 consecutive
        # creates leave 6 abandoned (the final one still active/excluded) - enough to exercise the
        # limit=5 cap without needing to force a real game to finish via guessing. Exact newest-
        # first ordering is already covered at the service layer
        # (TestGetRecentGames.test_orders_newest_first_and_caps_at_the_limit), which controls
        # created_at explicitly rather than relying on real wall-clock gaps between requests.
        games = [_create_game(client) for _ in range(7)]
        abandoned_ids = {g["id"] for g in games[:6]}

        response = client.get("/api/v1/games/recent")

        assert response.status_code == 200
        recent = response.json()["games"]
        assert len(recent) == 5
        assert {g["id"] for g in recent} <= abandoned_ids

    def test_the_first_of_two_games_for_the_same_mode_shows_up_once_abandoned(self, client):
        # End-to-end proof that the abandon side effect (GamesService._abandon_active_games) is
        # visible through the API, not just at the service layer.
        _register(client)
        first = _create_game(client)
        _create_game(client)

        response = client.get("/api/v1/games/recent")

        assert response.status_code == 200
        assert first["id"] in {g["id"] for g in response.json()["games"]}
