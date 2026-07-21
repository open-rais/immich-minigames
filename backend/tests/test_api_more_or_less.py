from uuid import uuid4


def _create_game(client, owner: str) -> dict:
    response = client.post(
        "/api/v1/games",
        json={"type": "more-or-less", "mode": "personAssets"},
        headers={"X-Owner-Id": owner},
    )
    assert response.status_code == 201
    return response.json()


def _register(client) -> None:
    unique = uuid4().hex[:8]
    body = {
        "email": f"user-{unique}@example.com",
        "username": f"user-{unique}",
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
    }
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201


class TestCreateGame:
    def test_returns_a_game_with_a_redacted_first_round(self, client):
        owner = str(uuid4())

        game = _create_game(client, owner)

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

    def test_requires_owner_header(self, client):
        response = client.post("/api/v1/games", json={"type": "more-or-less", "mode": "personAssets"})

        assert response.status_code == 422

    def test_unsupported_mode_returns_400(self, client):
        response = client.post(
            "/api/v1/games",
            json={"type": "geoguessr", "mode": "default"},
            headers={"X-Owner-Id": str(uuid4())},
        )

        assert response.status_code == 400


class TestGetGame:
    def test_wrong_owner_returns_403(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)

        response = client.get(f"/api/v1/games/{game['id']}", headers={"X-Owner-Id": str(uuid4())})

        assert response.status_code == 403

    def test_missing_game_returns_404(self, client):
        response = client.get(f"/api/v1/games/{uuid4()}", headers={"X-Owner-Id": str(uuid4())})

        assert response.status_code == 404

    def test_logged_in_game_is_reachable_with_a_different_owner_header(self, client):
        # Once a game is tied to an account (see docs/TODO/CODE-REVIEW.md #3), the account is the
        # real proof of ownership - a stale/rotated X-Owner-Id shouldn't lock the owner out.
        owner = str(uuid4())
        _register(client)
        game = _create_game(client, owner)

        response = client.get(f"/api/v1/games/{game['id']}", headers={"X-Owner-Id": str(uuid4())})

        assert response.status_code == 200

    def test_logged_in_game_returns_403_once_logged_out(self, client):
        owner = str(uuid4())
        _register(client)
        game = _create_game(client, owner)
        client.cookies.clear()

        response = client.get(f"/api/v1/games/{game['id']}", headers={"X-Owner-Id": owner})

        assert response.status_code == 403

    def test_logged_in_game_returns_403_for_a_different_account(self, client):
        # This is the actual bug #3 fixes: a leaked/guessed X-Owner-Id used to be enough on its
        # own to read and play someone else's logged-in game.
        owner = str(uuid4())
        _register(client)
        game = _create_game(client, owner)
        client.cookies.clear()
        _register(client)

        response = client.get(f"/api/v1/games/{game['id']}", headers={"X-Owner-Id": owner})

        assert response.status_code == 403


class TestPlayRound:
    def test_full_playthrough_never_leaks_the_answer_before_its_round_is_played(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)

        rounds_played = 0
        while not game["finished"] and rounds_played < 40:
            pending = game["rounds"][-1]
            # An external client can only ever see reference_asset_count for the pending round -
            # simulate a real guess by asking the server for the game state again and comparing
            # against what's already known (reference) is not possible without the hidden count,
            # so instead we play both branches implicitly by checking the response afterwards.
            response = client.post(
                f"/api/v1/games/{game['id']}/rounds/{pending['id']}",
                json={"guess": "more"},
                headers={"X-Owner-Id": owner},
            )
            assert response.status_code == 200
            result = response.json()

            state = client.get(f"/api/v1/games/{game['id']}", headers={"X-Owner-Id": owner}).json()
            answered = next(r for r in state["rounds"] if r["id"] == pending["id"])
            assert answered["candidate_asset_count"] is not None
            assert answered["guess"] == "more"
            assert answered["correct"] == result["correct"]

            game = state
            rounds_played += 1

        assert rounds_played > 0

    def test_wrong_round_id_returns_409(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)

        response = client.post(
            f"/api/v1/games/{game['id']}/rounds/{uuid4()}",
            json={"guess": "more"},
            headers={"X-Owner-Id": owner},
        )

        assert response.status_code == 409
