from uuid import uuid4


def _create_game(client) -> dict:
    response = client.post("/api/v1/games", json={"type": "trivium", "mode": "birthday"})
    assert response.status_code == 201
    return response.json()


class TestCreateGame:
    def test_returns_a_game_with_a_redacted_first_round(self, logged_client):
        game = _create_game(logged_client)

        assert game["score"] == 0
        assert game["finished"] is False
        assert len(game["rounds"]) == 1
        round_ = game["rounds"][0]
        assert round_["game_type"] == "trivium"
        assert round_["question_kind"] == "birthday_year"
        assert len(round_["alternatives"]) == 4
        assert round_["params"]["person_name"]
        # The answer isn't revealed before the round is played.
        assert round_["correct_index"] is None
        assert round_["guess"] is None
        assert round_["elapsed_ms"] is None
        assert round_["correct"] is None

    def test_without_a_cookie_returns_401(self, client):
        client.cookies.clear()

        response = client.post("/api/v1/games", json={"type": "trivium", "mode": "birthday"})

        assert response.status_code == 401

    def test_unsupported_mode_returns_400(self, logged_client):
        response = logged_client.post("/api/v1/games", json={"type": "trivium", "mode": "photos"})

        assert response.status_code == 400


class TestPlayRound:
    def test_answering_reveals_the_round_and_scores_accordingly(self, logged_client):
        # The correct index is redacted pre-answer (TestCreateGame above), so this can't force a
        # win - it just plays alternative 0 and checks the response is internally consistent with
        # whatever that turned out to be.
        game = _create_game(logged_client)
        pending = game["rounds"][0]

        response = logged_client.post(
            f"/api/v1/games/{game['id']}/rounds/{pending['id']}",
            json={"alternative": 0, "elapsed_ms": 0},
        )

        assert response.status_code == 200
        result = response.json()
        answered = result["answered_round"]
        assert answered["correct_index"] is not None
        assert answered["guess"] == 0
        assert answered["elapsed_ms"] == 0
        assert result["correct"] == (answered["guess"] == answered["correct_index"])
        # An instant (elapsed_ms=0) answer scores the full default max_points (TRIVIUM.md §3).
        assert result["score"] == (100 if result["correct"] else 0)
        assert result["finished"] == (not result["correct"])

    def test_a_timed_out_answer_ends_the_game(self, logged_client):
        game = _create_game(logged_client)
        pending = game["rounds"][0]

        response = logged_client.post(
            f"/api/v1/games/{game['id']}/rounds/{pending['id']}",
            json={"alternative": None, "elapsed_ms": 10_000},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["correct"] is False
        assert result["score_delta"] == 0
        assert result["finished"] is True
        assert result["answered_round"]["guess"] is None

    def test_full_playthrough_never_leaks_the_answer_before_its_round_is_played(self, logged_client):
        game = _create_game(logged_client)

        rounds_played = 0
        while not game["finished"] and rounds_played < 40:
            pending = game["rounds"][-1]

            response = logged_client.post(
                f"/api/v1/games/{game['id']}/rounds/{pending['id']}",
                json={"alternative": 0, "elapsed_ms": 0},
            )
            assert response.status_code == 200
            result = response.json()

            state = logged_client.get(f"/api/v1/games/{game['id']}").json()
            answered = next(r for r in state["rounds"] if r["id"] == pending["id"])
            assert answered["correct_index"] is not None
            assert answered["guess"] == 0
            assert answered["correct"] == result["correct"]

            game = state
            rounds_played += 1

        assert rounds_played > 0

    def test_wrong_round_id_returns_409(self, logged_client):
        game = _create_game(logged_client)

        response = logged_client.post(
            f"/api/v1/games/{game['id']}/rounds/{uuid4()}",
            json={"alternative": 0, "elapsed_ms": 0},
        )

        assert response.status_code == 409
