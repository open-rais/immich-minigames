"""Route-level HTTP-layer coverage for roadmap #G's player-facing daily endpoints
(api/daily_api.py) - GamesService-level behavior (challenge generation, world separation, scripted
replay) is already covered by test_daily_service.py/test_games_service_daily.py; this file only
checks status codes/response shape, mirroring test_api_current_and_recent_games.py's approach."""

from uuid import uuid4

import pytest

from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS
from persistence.daily import DailyConfigModel


@pytest.fixture(autouse=True)
def _clean_daily_config(db_session):
    def _clear():
        db_session.query(DailyConfigModel).filter(DailyConfigModel.game_type == GEOGUESSR_TYPE).delete()
        db_session.commit()

    _clear()
    yield
    _clear()


def _enable(db_session) -> None:
    db_session.add(DailyConfigModel(game_type=GEOGUESSR_TYPE, mode=MODE_DISTANCE_BETWEEN_GUESS, enabled=True, values={}))
    db_session.commit()


class TestGetDailyStatus:
    def test_lists_only_enabled_modes(self, client, db_session):
        _enable(db_session)

        response = client.get("/api/v1/daily", headers={"X-Owner-Id": str(uuid4())})

        assert response.status_code == 200
        body = response.json()
        assert "resets_at" in body
        assert "server_now" in body
        assert any(
            m["game_type"] == GEOGUESSR_TYPE and m["mode"] == MODE_DISTANCE_BETWEEN_GUESS for m in body["modes"]
        )

    def test_works_anonymously(self, client, db_session):
        _enable(db_session)

        response = client.get("/api/v1/daily", headers={"X-Owner-Id": str(uuid4())})

        assert response.status_code == 200

    def test_requires_owner_header(self, client, db_session):
        _enable(db_session)

        response = client.get("/api/v1/daily")

        assert response.status_code == 422


class TestCreateDailyGame:
    def test_not_enabled_returns_404(self, client):
        # A real, valid mode that just isn't enabled for the daily rotation (the cleanup fixture
        # guarantees no override is left over from another test) - a genuinely unsupported
        # game_type/mode combo instead returns 400 (see UnsupportedGameError), not this 404.
        response = client.post(
            f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/games", headers={"X-Owner-Id": str(uuid4())}
        )

        assert response.status_code == 404

    def test_unsupported_mode_returns_400(self, client):
        response = client.post(
            f"/api/v1/daily/{GEOGUESSR_TYPE}/not-a-real-mode/games", headers={"X-Owner-Id": str(uuid4())}
        )

        assert response.status_code == 400

    def test_creates_a_game(self, client, db_session):
        _enable(db_session)

        response = client.post(
            f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/games", headers={"X-Owner-Id": str(uuid4())}
        )

        assert response.status_code == 201
        body = response.json()
        assert body["daily_challenge_date"] is not None
        assert body["type"] == GEOGUESSR_TYPE
        assert body["mode"] == MODE_DISTANCE_BETWEEN_GUESS

    def test_second_attempt_by_the_same_owner_returns_409(self, client, db_session):
        _enable(db_session)
        owner = str(uuid4())

        first = client.post(
            f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/games", headers={"X-Owner-Id": owner}
        )
        assert first.status_code == 201

        second = client.post(
            f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/games", headers={"X-Owner-Id": owner}
        )
        assert second.status_code == 409

    def test_requires_owner_header(self, client, db_session):
        _enable(db_session)

        response = client.post(f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/games")

        assert response.status_code == 422

    def test_status_reflects_the_created_game(self, client, db_session):
        _enable(db_session)
        owner = str(uuid4())

        created = client.post(
            f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/games", headers={"X-Owner-Id": owner}
        ).json()

        status = client.get("/api/v1/daily", headers={"X-Owner-Id": owner}).json()
        mode_status = next(m for m in status["modes"] if m["game_type"] == GEOGUESSR_TYPE)

        assert mode_status["status"] == "in_progress"
        assert mode_status["game_id"] == created["id"]


class TestGetDailyLeaderboard:
    def test_a_date_with_no_challenge_returns_empty(self, client):
        response = client.get(f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/leaderboard")

        assert response.status_code == 200
        assert response.json()["entries"] == []

    def test_works_anonymously_and_defaults_to_today(self, client, db_session):
        _enable(db_session)

        response = client.get(f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/leaderboard")

        assert response.status_code == 200
        assert "date" in response.json()

    def test_accepts_an_explicit_date(self, client):
        response = client.get(
            f"/api/v1/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/leaderboard", params={"date": "2020-01-01"}
        )

        assert response.status_code == 200
        assert response.json() == {"date": "2020-01-01", "entries": []}
