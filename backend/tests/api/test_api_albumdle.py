from uuid import uuid4

import pytest
from conftest import mint_invite_code


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


def _create_game(logged_client) -> dict:
    response = logged_client.post("/api/v1/games", json={"type": "immichdle", "mode": "album"})
    assert response.status_code == 201
    return response.json()


def _play(logged_client, game_id: str, round_id: str, album_id) -> dict:
    response = logged_client.post(
        f"/api/v1/games/{game_id}/rounds/{round_id}",
        json={"album_id": str(album_id)},
    )
    return response


def _first_wrong_guess(logged_client, immich_service) -> tuple[str, object, str]:
    """Creates a game and guesses albums in order until the server confirms one is wrong - the
    target is redacted over the API, so it can't be excluded up front. Returns (game_id,
    wrong_album_id, next_round_id). Restarts on an accidental correct first guess. Mirrors
    test_api_immichdle.py's _first_wrong_guess exactly, substituting albums for people."""
    candidates = immich_service.get_albums(limit=100, min_asset_count=1)
    for _ in range(len(candidates)):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]
        for candidate in candidates:
            result = _play(logged_client, game["id"], round_id, candidate.id).json()
            if not result["correct"]:
                return game["id"], candidate.id, result["next_round"]["id"]
            game = _create_game(logged_client)
            round_id = game["rounds"][0]["id"]
    pytest.fail("could not find a wrong guess across the whole album pool")


def _play_until_finished(logged_client, immich_service) -> str:
    game = _create_game(logged_client)
    candidates = immich_service.get_albums(limit=100, min_asset_count=1)
    game_id = game["id"]
    round_id = game["rounds"][0]["id"]
    for candidate in candidates:
        result = _play(logged_client, game_id, round_id, candidate.id).json()
        if result["finished"]:
            return game_id
        round_id = result["next_round"]["id"]
    pytest.fail("game never finished after guessing every album")


class TestCreateGame:
    def test_returns_a_game_with_a_redacted_first_round(self, logged_client):
        game = _create_game(logged_client)

        assert game["score"] == 100
        assert game["finished"] is False
        assert game["target_album_id"] is None
        assert game["target_album_name"] is None
        assert game["target_album_asset_count"] is None
        assert game["target_album_first_asset_date"] is None
        assert len(game["rounds"]) == 1
        round_ = game["rounds"][0]
        assert round_["guess_album_id"] is None
        assert round_["correct"] is None
        assert round_["clues"] is None


class TestGetGame:
    def test_a_different_logged_in_account_returns_403(self, client):
        _register(client)
        game = _create_game(client)
        client.cookies.clear()
        _register(client)

        response = client.get(f"/api/v1/games/{game['id']}")

        assert response.status_code == 403


class TestPlayRound:
    def test_playing_a_round_reveals_clues_and_updates_score(self, logged_client, immich_service):
        game = _create_game(logged_client)
        pending_round_id = game["rounds"][0]["id"]
        [candidate] = immich_service.get_albums(randomize=True, limit=1, min_asset_count=1)

        response = _play(logged_client, game["id"], pending_round_id, candidate.id)

        assert response.status_code == 200
        result = response.json()
        answered = result["answered_round"]
        assert answered["guess_album_id"] == str(candidate.id)
        assert answered["guess_asset_count"] == candidate.asset_count
        assert answered["clues"] is not None
        pending_round = game["rounds"][0]
        assert pending_round["guess_asset_count"] is None
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

    def test_duplicate_guess_returns_400(self, logged_client, immich_service):
        game_id, wrong_id, next_round_id = _first_wrong_guess(logged_client, immich_service)

        response = _play(logged_client, game_id, next_round_id, wrong_id)

        assert response.status_code == 400

    def test_invalid_album_id_returns_400(self, logged_client):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]

        response = _play(logged_client, game["id"], round_id, uuid4())

        assert response.status_code == 400

    def test_wrong_round_id_returns_409(self, logged_client):
        game = _create_game(logged_client)

        response = _play(logged_client, game["id"], str(uuid4()), uuid4())

        assert response.status_code == 409

    def test_target_is_revealed_only_once_the_game_is_finished(self, logged_client, immich_service):
        game_id = _play_until_finished(logged_client, immich_service)

        state = logged_client.get(f"/api/v1/games/{game_id}").json()

        assert state["finished"] is True
        assert state["target_album_id"] is not None
        assert state["target_album_name"] is not None
        assert state["target_album_asset_count"] is not None
