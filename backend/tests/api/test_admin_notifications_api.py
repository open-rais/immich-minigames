import uuid
from uuid import UUID

from conftest import mint_invite_code

from config import Settings, get_settings
from main import app
from persistence.users import UserModel


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(client) -> dict:
    body = {
        "email": f"{_unique('user')}@example.com",
        "username": _unique("user"),
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
        "invite_code": mint_invite_code(),
    }
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    return {**body, "id": response.json()["id"]}


def _register_as_admin(client, db_session) -> dict:
    admin = _register(client)
    user = db_session.get(UserModel, UUID(admin["id"]))
    user.is_admin = True
    db_session.commit()
    return admin


def _settings_with_push_disabled() -> Settings:
    base = get_settings()
    return Settings(
        db_app_username=base.db_app_username,
        db_app_password=base.db_app_password,
        db_database_name=base.db_database_name,
        db_host=base.db_host,
        db_port=base.db_port,
        immich_api_key=base.immich_api_key,
        immich_server_url=base.immich_server_url,
        jwt_secret=base.jwt_secret,
        jwt_expire_days=base.jwt_expire_days,
        vapid_public_key=None,
        vapid_private_key=None,
        vapid_contact_email=None,
    )


class TestRunTick:
    def test_non_admin_returns_403(self, client):
        _register(client)
        response = client.post("/api/v1/admin/notifications/run-tick")
        assert response.status_code == 403

    def test_returns_503_when_push_is_not_configured(self, client, db_session):
        _register_as_admin(client, db_session)
        app.dependency_overrides[get_settings] = _settings_with_push_disabled
        try:
            response = client.post("/api/v1/admin/notifications/run-tick")
        finally:
            del app.dependency_overrides[get_settings]
        assert response.status_code == 503

    def test_an_admin_can_force_a_tick_at_a_simulated_time(self, client, db_session):
        _register_as_admin(client, db_session)
        # 16:00 falls outside all four slots' grace windows - this only proves the endpoint wires
        # through to a real tick without error, not that anything gets sent (see
        # tests/unit/services/test_notifications_schedule.py for the actual slot/rule coverage).
        response = client.post(
            "/api/v1/admin/notifications/run-tick", params={"now": "2026-01-01T16:00:00"}
        )
        assert response.status_code == 204
