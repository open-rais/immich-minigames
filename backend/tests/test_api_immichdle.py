from uuid import uuid4

import pytest


def _create_game(client, owner: str) -> dict:
    response = client.post(
        "/api/v1/games",
        json={"type": "immichdle", "mode": "person"},
        headers={"X-Owner-Id": owner},
    )
    assert response.status_code == 201
    return response.json()


def _play(client, game_id: str, round_id: str, owner: str, person_id) -> dict:
    response = client.post(
        f"/api/v1/games/{game_id}/rounds/{round_id}",
        json={"person_id": str(person_id)},
        headers={"X-Owner-Id": owner},
    )
    return response


def _first_wrong_guess(client, immich_service, owner: str) -> tuple[str, object, str]:
    """Creates a game and guesses named people in order until the server confirms one is wrong -
    the target is redacted over the API, so it can't be excluded up front. Returns
    (game_id, wrong_person_id, next_round_id). Restarts on an accidental correct first guess."""
    candidates = immich_service.get_persons(named_only=True, limit=100)
    for _ in range(len(candidates)):
        game = _create_game(client, owner)
        round_id = game["rounds"][0]["id"]
        for candidate in candidates:
            result = _play(client, game["id"], round_id, owner, candidate.id).json()
            if not result["correct"]:
                return game["id"], candidate.id, result["next_round"]["id"]
            game = _create_game(client, owner)
            round_id = game["rounds"][0]["id"]
    pytest.fail("could not find a wrong guess across the whole named-people pool")


def _play_until_finished(client, immich_service, owner: str) -> str:
    game = _create_game(client, owner)
    candidates = immich_service.get_persons(named_only=True, limit=100)
    game_id = game["id"]
    round_id = game["rounds"][0]["id"]
    for candidate in candidates:
        result = _play(client, game_id, round_id, owner, candidate.id).json()
        if result["finished"]:
            return game_id
        round_id = result["next_round"]["id"]
    pytest.fail("game never finished after guessing every named person")


class TestCreateGame:
    def test_returns_a_game_with_a_redacted_first_round(self, client):
        owner = str(uuid4())

        game = _create_game(client, owner)

        assert game["score"] == 100
        assert game["finished"] is False
        assert game["target_person_id"] is None
        assert game["target_person_name"] is None
        assert len(game["rounds"]) == 1
        round_ = game["rounds"][0]
        assert round_["guess_person_id"] is None
        assert round_["correct"] is None
        assert round_["clues"] is None


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
    def test_playing_a_round_reveals_clues_and_updates_score(self, client, immich_service):
        owner = str(uuid4())
        game = _create_game(client, owner)
        pending_round_id = game["rounds"][0]["id"]
        [candidate] = immich_service.get_persons(named_only=True, random=True, limit=1)

        response = _play(client, game["id"], pending_round_id, owner, candidate.id)

        assert response.status_code == 200
        result = response.json()
        answered = result["answered_round"]
        assert answered["guess_person_id"] == str(candidate.id)
        assert answered["guess_asset_count"] == candidate.asset_count
        assert answered["clues"] is not None
        pending_round = game["rounds"][0]
        assert pending_round["guess_asset_count"] is None
        assert pending_round["guess_birth_date"] is None
        assert pending_round["guess_first_asset_date"] is None
        if result["correct"]:
            assert result["score_delta"] == 0
            assert result["score"] == 100
            assert result["finished"] is True
            assert result["next_round"] is None
        else:
            assert result["score_delta"] == -5
            assert result["score"] == 95
            assert result["finished"] is False
            assert result["next_round"] is not None

    def test_duplicate_guess_returns_400(self, client, immich_service):
        owner = str(uuid4())
        game_id, wrong_id, next_round_id = _first_wrong_guess(client, immich_service, owner)

        response = _play(client, game_id, next_round_id, owner, wrong_id)

        assert response.status_code == 400

    def test_invalid_person_id_returns_400(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)
        round_id = game["rounds"][0]["id"]

        response = _play(client, game["id"], round_id, owner, uuid4())

        assert response.status_code == 400

    def test_wrong_round_id_returns_409(self, client):
        owner = str(uuid4())
        game = _create_game(client, owner)

        response = _play(client, game["id"], str(uuid4()), owner, uuid4())

        assert response.status_code == 409

    def test_target_is_revealed_only_once_the_game_is_finished(self, client, immich_service):
        owner = str(uuid4())
        game_id = _play_until_finished(client, immich_service, owner)

        state = client.get(f"/api/v1/games/{game_id}", headers={"X-Owner-Id": owner}).json()

        assert state["finished"] is True
        assert state["target_person_id"] is not None
        assert state["target_person_name"] is not None
