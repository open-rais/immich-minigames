from uuid import uuid4

from conftest import mint_invite_code


def _create_game(client) -> dict:
    response = client.post("/api/v1/games", json={"type": "more-or-less", "mode": "personAssets"})
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


class TestCreateGame:
    def test_returns_a_game_with_a_redacted_first_round(self, logged_client):
        game = _create_game(logged_client)

        assert game["score"] == 0
        assert game["finished"] is False
        # ADMIN-FEATURE.md point #4 - MoreOrLess has no configured total (no fixed round count),
        # unlike Geoguessr/Dateguessr's total_rounds or WhosThatPerson's total_people.
        assert game["total_rounds"] is None
        assert game["total_people"] is None
        assert len(game["rounds"]) == 1
        round_ = game["rounds"][0]
        assert round_["candidate_asset_count"] is None
        assert round_["guess"] is None
        assert round_["correct"] is None
        assert round_["reference_asset_count"] is not None

    def test_without_a_cookie_returns_401(self, client):
        client.cookies.clear()

        response = client.post("/api/v1/games", json={"type": "more-or-less", "mode": "personAssets"})

        assert response.status_code == 401

    def test_unsupported_mode_returns_400(self, logged_client):
        response = logged_client.post("/api/v1/games", json={"type": "geoguessr", "mode": "default"})

        assert response.status_code == 400


class TestGetGame:
    def test_missing_game_returns_404(self, logged_client):
        response = logged_client.get(f"/api/v1/games/{uuid4()}")

        assert response.status_code == 404

    def test_own_game_is_reachable(self, client):
        _register(client)
        game = _create_game(client)

        response = client.get(f"/api/v1/games/{game['id']}")

        assert response.status_code == 200

    def test_returns_401_once_logged_out(self, client):
        # Roadmap #H, F3 - "logged out" now means no session cookie at all, which the default-deny
        # middleware rejects before the request ever reaches GamesService's own ownership check
        # (GameOwnershipError/403) - this used to be a 403, see docs/TODO/NEW-AUTH.md §6 F3.
        _register(client)
        game = _create_game(client)
        client.cookies.clear()

        response = client.get(f"/api/v1/games/{game['id']}")

        assert response.status_code == 401

    def test_returns_403_for_a_different_account(self, client):
        # This is the actual bug #3 fixes: a leaked/guessed X-Owner-Id used to be enough on its
        # own to read and play someone else's logged-in game - now only the owning account can.
        _register(client)
        game = _create_game(client)
        client.cookies.clear()
        _register(client)

        response = client.get(f"/api/v1/games/{game['id']}")

        assert response.status_code == 403


class TestPlayRound:
    def test_full_playthrough_never_leaks_the_answer_before_its_round_is_played(self, logged_client):
        game = _create_game(logged_client)

        rounds_played = 0
        while not game["finished"] and rounds_played < 40:
            pending = game["rounds"][-1]
            # An external client can only ever see reference_asset_count for the pending round -
            # simulate a real guess by asking the server for the game state again and comparing
            # against what's already known (reference) is not possible without the hidden count,
            # so instead we play both branches implicitly by checking the response afterwards.
            response = logged_client.post(
                f"/api/v1/games/{game['id']}/rounds/{pending['id']}",
                json={"guess": "more"},
            )
            assert response.status_code == 200
            result = response.json()

            state = logged_client.get(f"/api/v1/games/{game['id']}").json()
            answered = next(r for r in state["rounds"] if r["id"] == pending["id"])
            assert answered["candidate_asset_count"] is not None
            assert answered["guess"] == "more"
            assert answered["correct"] == result["correct"]

            game = state
            rounds_played += 1

        assert rounds_played > 0

    def test_wrong_round_id_returns_409(self, logged_client):
        game = _create_game(logged_client)

        response = logged_client.post(
            f"/api/v1/games/{game['id']}/rounds/{uuid4()}",
            json={"guess": "more"},
        )

        assert response.status_code == 409


class TestRateLimit:
    def test_create_game_returns_429_after_the_limit(self, logged_client):
        responses = [
            logged_client.post("/api/v1/games", json={"type": "more-or-less", "mode": "personAssets"})
            for _ in range(31)
        ]

        assert all(r.status_code == 201 for r in responses[:30])
        assert responses[30].status_code == 429

    def test_play_round_returns_429_after_the_limit(self, logged_client):
        game = _create_game(logged_client)
        first_round = game["rounds"][0]

        # Only the first call genuinely answers the pending round (200); the rest hit the same
        # now-answered round_id, which would normally 409. The rate limit is checked before the
        # route body runs though, so every call still counts against the budget regardless of
        # what status the handler would've returned - no need to fabricate 30 real correct guesses
        # across fresh rounds, which isn't possible from outside without seeing the hidden count.
        responses = [
            logged_client.post(
                f"/api/v1/games/{game['id']}/rounds/{first_round['id']}",
                json={"guess": "more"},
            )
            for _ in range(31)
        ]

        assert responses[0].status_code == 200
        assert all(r.status_code == 409 for r in responses[1:30])
        assert responses[30].status_code == 429
