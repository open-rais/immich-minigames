import uuid
from uuid import UUID

import pytest

from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS
from persistence.daily import DailyConfigModel
from persistence.users import UserModel


@pytest.fixture(autouse=True)
def _clean_daily_configs(db_session):
    def _clear():
        db_session.query(DailyConfigModel).filter(DailyConfigModel.game_type == GEOGUESSR_TYPE).delete()
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


class TestListDailySettings:
    def test_anonymous_returns_401(self, client):
        client.cookies.clear()

        response = client.get("/api/v1/admin/daily/settings")

        assert response.status_code == 401

    def test_non_admin_returns_403(self, client):
        _register(client)

        response = client.get("/api/v1/admin/daily/settings")

        assert response.status_code == 403

    def test_admin_lists_every_mode_disabled_by_default(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.get("/api/v1/admin/daily/settings")

        assert response.status_code == 200
        by_mode = {(g["game_type"], g["mode"]): g for g in response.json()}
        geo = by_mode[(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)]
        assert geo["enabled"] is False
        keys = {s["key"] for s in geo["settings"]}
        assert "no_repeat_days" in keys
        assert "decay_km" in keys


class TestUpdateDailySettings:
    def test_admin_can_enable_a_mode(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put(f"/api/v1/admin/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}", json={"enabled": True})

        assert response.status_code == 200
        assert response.json()["enabled"] is True

    def test_admin_can_update_a_value(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put(
            f"/api/v1/admin/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}", json={"values": {"no_repeat_days": 10}}
        )

        assert response.status_code == 200
        settings = {s["key"]: s["value"] for s in response.json()["settings"]}
        assert settings["no_repeat_days"] == 10

    def test_non_admin_returns_403(self, client):
        _register(client)

        response = client.put(f"/api/v1/admin/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}", json={"enabled": True})

        assert response.status_code == 403

    def test_unknown_key_returns_400(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put(
            f"/api/v1/admin/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}", json={"values": {"not_a_real_key": 1}}
        )

        assert response.status_code == 400

    def test_unknown_game_type_returns_404(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.put(f"/api/v1/admin/daily/not-a-real-game/{MODE_DISTANCE_BETWEEN_GUESS}", json={"enabled": True})

        assert response.status_code == 404


class TestResetDailySettings:
    def test_reset_clears_values_but_keeps_enabled(self, client, db_session):
        _register_as_admin(client, db_session)
        client.put(
            f"/api/v1/admin/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}",
            json={"enabled": True, "values": {"no_repeat_days": 10}},
        )

        response = client.post(f"/api/v1/admin/daily/{GEOGUESSR_TYPE}/{MODE_DISTANCE_BETWEEN_GUESS}/reset")

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        settings = {s["key"]: s["value"] for s in body["settings"]}
        assert settings["no_repeat_days"] == 30

    def test_unknown_game_type_returns_404(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.post(f"/api/v1/admin/daily/not-a-real-game/{MODE_DISTANCE_BETWEEN_GUESS}/reset")

        assert response.status_code == 404
