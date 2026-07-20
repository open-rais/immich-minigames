from uuid import uuid4

import pytest


def _create_game(client, owner: str) -> dict:
    response = client.post(
        "/api/v1/games",
        json={"type": "whos-that-person", "mode": "namedFaces"},
        headers={"X-Owner-Id": owner},
    )
    assert response.status_code == 201
    return response.json()


def _play(client, game_id: str, round_id: str, owner: str, guesses: dict) -> dict:
    return client.post(
        f"/api/v1/games/{game_id}/rounds/{round_id}",
        json={"guesses": {str(k): str(v) for k, v in guesses.items()}},
        headers={"X-Owner-Id": owner},
    )


class TestCreateGame:
    def test_returns_a_game_with_a_redacted_first_round(self, client):
        owner = str(uuid4())

        game = _create_game(client, owner)

        assert game["score"] == 0
        assert game["finished"] is False
        # ADMIN-FEATURE.md point #4 - the live configured total, not a hardcoded frontend mirror.
        assert game["total_people"] == 15
        assert len(game["rounds"]) == 1
        round_ = game["rounds"][0]
        assert round_["correct"] is None
        assert 1 <= len(round_["faces"]) <= 5
        for face in round_["faces"]:
            assert face["person_id"] is None
            assert face["person_name"] is None
            assert face["correct"] is None
            assert face["image_width"] > 0
            assert face["bounding_box_x2"] > face["bounding_box_x1"]


class TestGetGame:
    def test_wrong_owner_returns_403(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)

        response = client.get(f"/api/v1/games/{game['id']}", headers={"X-Owner-Id": str(uuid4())})

        assert response.status_code == 403

    def test_missing_game_returns_404(self, client):
        response = client.get(f"/api/v1/games/{uuid4()}", headers={"X-Owner-Id": str(uuid4())})

        assert response.status_code == 404


class TestPlayRound:
    def test_correct_guesses_reveal_answers_and_update_score(self, client, games_service):
        owner = str(uuid4())
        game = _create_game(client, owner)
        round_id = game["rounds"][0]["id"]

        # Play through the domain layer to get the true, unredacted answers for this round (the
        # API never reveals them pre-answer), then submit those same guesses over HTTP.
        domain_game = games_service.get_game(game["id"], owner)
        first_round = domain_game.current_round
        guesses = {face.face_id: face.person_id for face in first_round.faces}

        response = _play(client, game["id"], round_id, owner, guesses)

        assert response.status_code == 200
        result = response.json()
        assert result["correct"] is True
        assert result["score_delta"] == sum(range(1, len(guesses) + 1))
        assert result["score"] == result["score_delta"]
        assert result["finished"] is False
        answered = result["answered_round"]
        for face in answered["faces"]:
            assert face["person_id"] is not None
            assert face["correct"] is True

    def test_wrong_guess_is_revealed_as_incorrect(self, client, games_service):
        owner = str(uuid4())
        game = _create_game(client, owner)
        round_id = game["rounds"][0]["id"]
        domain_game = games_service.get_game(game["id"], owner)
        first_round = domain_game.current_round
        guesses = {face.face_id: uuid4() for face in first_round.faces}

        response = _play(client, game["id"], round_id, owner, guesses)

        assert response.status_code == 200
        result = response.json()
        assert result["correct"] is False
        assert result["score_delta"] == 0
        assert result["finished"] is False

    def test_incomplete_guess_returns_422(self, client, games_service):
        owner = str(uuid4())
        game = _create_game(client, owner)
        round_id = game["rounds"][0]["id"]
        domain_game = games_service.get_game(game["id"], owner)
        [first_face, *_] = domain_game.current_round.faces

        response = _play(client, game["id"], round_id, owner, {first_face.face_id: first_face.person_id})

        if len(domain_game.current_round.faces) == 1:
            pytest.skip("round only had one face - a single-entry guess is actually complete here")
        assert response.status_code == 422

    def test_wrong_round_id_returns_409(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)

        response = _play(client, game["id"], str(uuid4()), owner, {uuid4(): uuid4()})

        assert response.status_code == 409
