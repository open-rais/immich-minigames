from uuid import uuid4


def _create_game(client, owner: str) -> dict:
    response = client.post(
        "/api/v1/games",
        json={"type": "geoguessr", "mode": "distanceBetweenGuess"},
        headers={"X-Owner-Id": owner},
    )
    assert response.status_code == 201
    return response.json()


class TestCreateGame:
    def test_returns_a_game_with_a_redacted_first_round(self, client):
        owner = str(uuid4())

        game = _create_game(client, owner)

        assert game["score"] == 0
        assert game["finished"] is False
        assert len(game["rounds"]) == 1
        round_ = game["rounds"][0]
        assert round_["game_type"] == "geoguessr"
        assert round_["actual_latitude"] is None
        assert round_["actual_longitude"] is None
        assert round_["distance_km"] is None
        assert round_["score_delta"] is None
        assert round_["asset_id"] is not None


class TestPlayRound:
    def test_full_playthrough_reveals_actual_location_and_ends_after_five_rounds(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)

        rounds_played = 0
        while not game["finished"] and rounds_played < 10:
            pending = game["rounds"][-1]

            response = client.post(
                f"/api/v1/games/{game['id']}/rounds/{pending['id']}",
                json={"latitude": 0.0, "longitude": 0.0},
                headers={"X-Owner-Id": owner},
            )
            assert response.status_code == 200
            result = response.json()
            assert result["correct"] is None  # not a binary-guess game

            state = client.get(f"/api/v1/games/{game['id']}", headers={"X-Owner-Id": owner}).json()
            answered = next(r for r in state["rounds"] if r["id"] == pending["id"])
            assert answered["actual_latitude"] is not None
            assert answered["actual_longitude"] is not None
            assert answered["distance_km"] is not None
            assert answered["score_delta"] == result["score_delta"]

            game = state
            rounds_played += 1

        assert rounds_played == 5
        assert game["finished"] is True

    def test_wrong_round_id_returns_409(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)

        response = client.post(
            f"/api/v1/games/{game['id']}/rounds/{uuid4()}",
            json={"game_type": "geoguessr", "latitude": 0.0, "longitude": 0.0},
            headers={"X-Owner-Id": owner},
        )

        assert response.status_code == 409

    def test_out_of_range_latitude_returns_422(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)
        pending = game["rounds"][-1]

        response = client.post(
            f"/api/v1/games/{game['id']}/rounds/{pending['id']}",
            json={"latitude": 200.0, "longitude": 0.0},
            headers={"X-Owner-Id": owner},
        )

        assert response.status_code == 422

    def test_out_of_range_longitude_returns_422(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)
        pending = game["rounds"][-1]

        response = client.post(
            f"/api/v1/games/{game['id']}/rounds/{pending['id']}",
            json={"latitude": 0.0, "longitude": -200.0},
            headers={"X-Owner-Id": owner},
        )

        assert response.status_code == 422
