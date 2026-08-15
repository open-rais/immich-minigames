from uuid import UUID, uuid4

import pytest
from conftest import mint_invite_code

from persistence.games import GameModel
from persistence.users import UserModel


def _create_game(client) -> dict:
    response = client.post("/api/v1/games", json={"type": "whos-that-person", "mode": "namedFaces"})
    assert response.status_code == 201
    return response.json()


def _play(client, game_id: str, round_id: str, guesses: dict) -> dict:
    return client.post(
        f"/api/v1/games/{game_id}/rounds/{round_id}",
        json={"guesses": {str(k): str(v) for k, v in guesses.items()}},
    )


def _owning_user(db_session, game_id: str) -> UserModel:
    # Every game is created by a logged-in account (see _create_game's caller, logged_client), so
    # GamesService.get_game's own ownership check (services/games_service.py's _load_game) needs a
    # matching UserModel. Looked up by the game's own user_id rather than threading the account
    # through every caller - logged_client's own fixture only ever exposes the HTTP client, not
    # which account it registered as.
    game_row = db_session.get(GameModel, UUID(game_id))
    return db_session.get(UserModel, game_row.user_id)


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
        # The live configured total, not a hardcoded frontend mirror.
        assert game["total_people"] == 15
        assert len(game["rounds"]) == 1
        round_ = game["rounds"][0]
        assert round_["correct"] is None
        assert 1 <= len(round_["faces"]) <= 5
        for face in round_["faces"]:
            assert face["person_id"] is None
            assert face["person_name"] is None
            assert face["correct"] is None
            assert face["guess_person_id"] is None
            assert face["guess_person_name"] is None
            assert face["image_width"] > 0
            assert face["bounding_box_x2"] > face["bounding_box_x1"]


class TestGetGame:
    def test_a_different_logged_in_account_returns_403(self, client):
        _register(client)
        game = _create_game(client)
        client.cookies.clear()
        _register(client)

        response = client.get(f"/api/v1/games/{game['id']}")

        assert response.status_code == 403

    def test_missing_game_returns_404(self, logged_client):
        response = logged_client.get(f"/api/v1/games/{uuid4()}")

        assert response.status_code == 404


class TestPlayRound:
    def test_correct_guesses_reveal_answers_and_update_score(self, logged_client, games_service, db_session):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]

        # Play through the domain layer to get the true, unredacted answers for this round (the
        # API never reveals them pre-answer), then submit those same guesses over HTTP.
        domain_game = games_service.get_game(game["id"], _owning_user(db_session, game["id"]))
        first_round = domain_game.current_round
        guesses = {face.face_id: face.person_id for face in first_round.faces}
        # _load_game reads the row with SELECT ... FOR UPDATE - this inspection-only read would
        # otherwise hold that lock for the rest of the test (games_service here shares db_session,
        # only closed at teardown) and deadlock against the HTTP call below, which loads the same
        # game_id through its own request-scoped session.
        db_session.rollback()

        response = _play(logged_client, game["id"], round_id, guesses)

        assert response.status_code == 200
        result = response.json()
        assert result["correct"] is True
        # Flat count (streak_scoring defaults to off, see docs/TODO/MINOR-FIXES.md #1) - one point
        # per correctly guessed face, not the combo streak sum.
        assert result["score_delta"] == len(guesses)
        assert result["score"] == result["score_delta"]
        assert result["finished"] is False
        answered = result["answered_round"]
        for face in answered["faces"]:
            assert face["person_id"] is not None
            assert face["correct"] is True
            # Guessed the true person_id, a real named person, so both are resolved.
            assert face["guess_person_id"] == str(guesses[UUID(face["face_id"])])
            assert face["guess_person_name"] is not None

    def test_wrong_guess_is_revealed_as_incorrect(self, logged_client, games_service, db_session):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]
        domain_game = games_service.get_game(game["id"], _owning_user(db_session, game["id"]))
        first_round = domain_game.current_round
        guesses = {face.face_id: uuid4() for face in first_round.faces}
        db_session.rollback()  # release the FOR UPDATE lock - see the comment above for why

        response = _play(logged_client, game["id"], round_id, guesses)

        assert response.status_code == 200
        result = response.json()
        assert result["correct"] is False
        assert result["score_delta"] == 0
        assert result["finished"] is False
        for face in result["answered_round"]["faces"]:
            # The guess itself is always shown (guess_person_id == what was submitted), but these
            # are random uuid4()s, so none resolve to a real person's name.
            assert face["guess_person_id"] == str(guesses[UUID(face["face_id"])])
            assert face["guess_person_name"] is None

    def test_incomplete_guess_returns_422(self, logged_client, games_service, db_session):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]
        domain_game = games_service.get_game(game["id"], _owning_user(db_session, game["id"]))
        [first_face, *_] = domain_game.current_round.faces
        db_session.rollback()  # release the FOR UPDATE lock - see the comment above for why

        response = _play(logged_client, game["id"], round_id, {first_face.face_id: first_face.person_id})

        if len(domain_game.current_round.faces) == 1:
            pytest.skip("round only had one face - a single-entry guess is actually complete here")
        assert response.status_code == 422

    def test_wrong_round_id_returns_409(self, logged_client):
        game = _create_game(logged_client)

        response = _play(logged_client, game["id"], str(uuid4()), {uuid4(): uuid4()})

        assert response.status_code == 409
