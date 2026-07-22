import uuid
from uuid import UUID

import pytest

from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from persistence.game_settings import GameSettingsModel
from persistence.users import UserModel


@pytest.fixture(autouse=True)
def _clean_geoguessr_settings(db_session):
    # Unlike the user tests in this file (isolated from each other via _unique() emails/
    # usernames), game_settings rows are keyed by a fixed game_type - every test here that
    # persists a Geoguessr override shares the same row, so leaving one dirty would leak into
    # later tests (in this file or, since this DB isn't reset between test files, any other file
    # that assumes Geoguessr's defaults - see test_api_geoguessr.py/test_game_settings_service.py).
    def _clear():
        db_session.query(GameSettingsModel).filter(GameSettingsModel.game_type == GEOGUESSR_TYPE).delete()
        db_session.commit()

    _clear()
    yield
    _clear()


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(client, **overrides) -> dict:
    body = {
        "email": f"{_unique('user')}@example.com",
        "username": _unique("user"),
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
    }
    body.update(overrides)
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    return {**body, "id": response.json()["id"]}


def _register_as_admin(client, db_session) -> dict:
    admin = _register(client)
    user = db_session.get(UserModel, UUID(admin["id"]))
    user.is_admin = True
    db_session.commit()
    return admin


class TestListGameSettings:
    def test_anonymous_returns_401(self, client):
        client.cookies.clear()

        response = client.get("/api/v1/admin/games/settings")

        assert response.status_code == 401

    def test_non_admin_returns_403(self, client):
        _register(client)

        response = client.get("/api/v1/admin/games/settings")

        assert response.status_code == 403

    def test_admin_lists_every_game_including_ones_with_no_settings(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.get("/api/v1/admin/games/settings")

        assert response.status_code == 200
        by_type = {g["game_type"]: g for g in response.json()}
        assert MORE_OR_LESS_TYPE in by_type
        assert by_type[MORE_OR_LESS_TYPE]["settings"] == []
        geo_keys = {s["key"] for s in by_type[GEOGUESSR_TYPE]["settings"]}
        assert "decay_km" in geo_keys


class TestUpdateGameSettings:
    def test_admin_can_update_a_setting(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put(f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings", json={"decay_km": 900.0})

        assert response.status_code == 200
        settings = {s["key"]: s["value"] for s in response.json()["settings"]}
        assert settings["decay_km"] == 900.0

    def test_non_admin_returns_403(self, client):
        _register(client)

        response = client.put(f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings", json={"decay_km": 900.0})

        assert response.status_code == 403

    def test_unknown_key_returns_400(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put(f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings", json={"not_a_real_key": 1})

        assert response.status_code == 400

    def test_value_below_min_returns_400(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put(f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings", json={"total_rounds": 0})

        assert response.status_code == 400

    def test_value_above_max_returns_400(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put(f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings", json={"total_rounds": 51})

        assert response.status_code == 400

    def test_nan_value_returns_400(self, client, db_session):
        # httpx's own json= kwarg refuses to encode NaN client-side (allow_nan=False) - send the
        # raw body instead, since Python's stdlib json (what actually parses the request server
        # side) accepts the NaN literal, and a handcrafted request isn't bound by httpx's opinion.
        _register_as_admin(client, db_session)

        response = client.put(
            f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings",
            content=b'{"decay_km": NaN}',
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400

    def test_unknown_game_type_returns_404(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put("/api/v1/admin/games/not-a-real-game/settings", json={"decay_km": 900.0})

        assert response.status_code == 404


class TestGameSettingsAffectNewGames:
    """End-to-end - an admin override actually reaches GameOut.total_rounds (see api/dto/common.py
    and games/asset_rounds.py's total_rounds property), not just what GameSettingsService reports
    in isolation (test_game_settings_service.py) or what the admin endpoint echoes back."""

    def test_total_rounds_override_is_reflected_in_a_newly_created_game(self, client, db_session):
        _register_as_admin(client, db_session)
        client.put(f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings", json={"total_rounds": 2})

        game = client.post(
            "/api/v1/games",
            json={"type": GEOGUESSR_TYPE, "mode": "distanceBetweenGuess"},
            headers={"X-Owner-Id": str(uuid.uuid4())},
        ).json()

        assert game["total_rounds"] == 2


class TestResetGameSettings:
    def test_admin_can_reset_a_previously_changed_setting(self, client, db_session):
        _register_as_admin(client, db_session)
        client.put(f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings", json={"decay_km": 900.0})

        response = client.post(f"/api/v1/admin/games/{GEOGUESSR_TYPE}/settings/reset")

        assert response.status_code == 200
        settings = {s["key"]: s["value"] for s in response.json()["settings"]}
        assert settings["decay_km"] == 1500.0

    def test_unknown_game_type_returns_404(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.post("/api/v1/admin/games/not-a-real-game/settings/reset")

        assert response.status_code == 404
