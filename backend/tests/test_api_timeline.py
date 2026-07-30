import pytest
from uuid import UUID, uuid4

from conftest import mint_invite_code
from games.timeline import TOLERANCE_DAYS
from persistence.games import GameModel
from persistence.users import UserModel


def _create_game(client) -> dict:
    response = client.post("/api/v1/games", json={"type": "timeline", "mode": "arcade"})
    assert response.status_code == 201
    return response.json()


def _play(client, game_id: str, round_id: str, slot: int) -> dict:
    return client.post(f"/api/v1/games/{game_id}/rounds/{round_id}", json={"slot": slot})


def _owning_user(db_session, game_id: str) -> UserModel:
    # Mirrors test_api_whos_that_person.py's helper - every game is created by a logged-in account
    # (logged_client), so GamesService.get_game's ownership check needs a matching UserModel.
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
        assert len(game["rounds"]) == 1
        round_ = game["rounds"][0]
        assert round_["game_type"] == "timeline"
        assert len(round_["board"]) == 1
        assert round_["board"][0]["date"] is not None  # the starting card's date is never secret
        assert round_["card_asset_id"] is not None
        assert round_["guess_slot"] is None
        assert round_["card_date"] is None
        assert round_["correct_slot"] is None
        assert round_["correct"] is None
        assert round_["score_delta"] is None

    def test_without_a_cookie_returns_401(self, client):
        client.cookies.clear()

        response = client.post("/api/v1/games", json={"type": "timeline", "mode": "arcade"})

        assert response.status_code == 401


class TestPlayRound:
    def test_correct_guess_reveals_the_answer_and_grows_the_next_round_board(
        self, logged_client, games_service, db_session
    ):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]

        # Play through the domain layer to get the true, unredacted answer for this round (the API
        # never reveals it pre-answer), then submit that same guess over HTTP.
        domain_game = games_service.get_game(game["id"], _owning_user(db_session, game["id"]))
        first_round = domain_game.current_round
        correct_slot = first_round.correct_slot
        # _load_game reads the row with SELECT ... FOR UPDATE (docs/TODO/CODE-REVIEW.md #6) - this
        # inspection-only read would otherwise hold that lock for the rest of the test (games_service
        # here shares db_session, only closed at teardown) and deadlock against the HTTP call below,
        # which loads the same game_id through its own request-scoped session.
        db_session.rollback()

        response = _play(logged_client, game["id"], round_id, correct_slot)

        assert response.status_code == 200
        result = response.json()
        assert result["correct"] is True
        assert result["score_delta"] == 1
        assert result["score"] == 1
        assert result["finished"] is False
        answered = result["answered_round"]
        assert answered["card_date"] is not None
        assert answered["correct_slot"] == correct_slot
        assert answered["guess_slot"] == correct_slot
        assert len(answered["board"]) == 1  # the answered round's own board doesn't grow
        assert result["next_round"] is not None
        assert len(result["next_round"]["board"]) == 2

    def test_wrong_guess_ends_the_game(self, logged_client, games_service, db_session):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]

        domain_game = games_service.get_game(game["id"], _owning_user(db_session, game["id"]))
        first_round = domain_game.current_round
        accepted = set(first_round.accepted_slots(TOLERANCE_DAYS))
        db_session.rollback()

        if accepted == {0, 1}:
            # Both slots of a board-of-1 game are only ever both accepted when the drawn card ties
            # the starting card's date exactly (docs/TODO/TIMELINE.md decision [D]) - there's no
            # "wrong" slot to submit in that case.
            pytest.skip("both slots tied - no wrong slot exists for this round")
        wrong_slot = next(slot for slot in (0, 1) if slot not in accepted)

        response = _play(logged_client, game["id"], round_id, wrong_slot)

        assert response.status_code == 200
        result = response.json()
        assert result["correct"] is False
        assert result["score_delta"] == 0
        assert result["finished"] is True
        assert result["next_round"] is None
        assert result["answered_round"]["card_date"] is not None

    def test_wrong_round_id_returns_409(self, logged_client):
        game = _create_game(logged_client)

        response = _play(logged_client, game["id"], str(uuid4()), 0)

        assert response.status_code == 409

    def test_slot_beyond_the_board_returns_422(self, logged_client):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]
        board_len = len(game["rounds"][0]["board"])

        response = _play(logged_client, game["id"], round_id, board_len + 1)

        assert response.status_code == 422

    def test_negative_slot_returns_422(self, logged_client):
        game = _create_game(logged_client)
        round_id = game["rounds"][0]["id"]

        response = _play(logged_client, game["id"], round_id, -1)

        assert response.status_code == 422


class TestCurrentGame:
    def test_creating_a_second_game_abandons_the_first_and_current_returns_it(self, logged_client):
        first = _create_game(logged_client)
        second = _create_game(logged_client)

        response = logged_client.get("/api/v1/games/current", params={"game_type": "timeline", "mode": "arcade"})

        assert response.status_code == 200
        assert response.json()["game"]["id"] == second["id"]
        assert second["id"] != first["id"]
