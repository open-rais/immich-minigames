from uuid import UUID, uuid4

from config import Settings, get_settings
from main import app
from persistence.notifications import PushSubscriptionModel


def _settings_with_push_disabled() -> Settings:
    # Same pattern as test_api_config.py's _settings_with_vapid(None, None, None) - explicit, not
    # a bare Settings() relying on the ambient .env having no VAPID_* set (it does, on any machine
    # that's actually configured push for manual testing).
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


class TestPreferences:
    def test_get_returns_defaults_before_any_put(self, logged_client):
        response = logged_client.get("/api/v1/notifications/preferences")

        assert response.status_code == 200
        assert response.json() == {
            "daily_reminders": False,
            "birthdays": False,
            "album_anniversary": False,
            "language": "en",
        }

    def test_put_then_get_round_trips(self, logged_client):
        body = {"daily_reminders": True, "birthdays": True, "album_anniversary": False, "language": "es"}

        put_response = logged_client.put("/api/v1/notifications/preferences", json=body)
        assert put_response.status_code == 200
        assert put_response.json() == body

        get_response = logged_client.get("/api/v1/notifications/preferences")
        assert get_response.json() == body


class TestSubscribe:
    def test_rejects_a_non_https_endpoint(self, logged_client):
        response = logged_client.post(
            "/api/v1/notifications/subscriptions",
            json={"endpoint": "http://fcm.googleapis.com/send/abc", "keys": {"p256dh": "p", "auth": "a"}},
        )

        assert response.status_code == 400

    def test_rejects_an_endpoint_host_outside_the_allowlist(self, logged_client):
        response = logged_client.post(
            "/api/v1/notifications/subscriptions",
            json={"endpoint": "https://evil.example.com/send/abc", "keys": {"p256dh": "p", "auth": "a"}},
        )

        assert response.status_code == 400

    def test_unsubscribe_of_a_never_subscribed_endpoint_is_a_no_op_204(self, logged_client):
        response = logged_client.request(
            "DELETE", "/api/v1/notifications/subscriptions", json={"endpoint": "https://fcm.googleapis.com/x"}
        )

        assert response.status_code == 204


class TestSendTest:
    def test_returns_404_with_no_subscriptions(self, logged_client):
        response = logged_client.post("/api/v1/notifications/test")

        assert response.status_code == 404

    def test_returns_503_when_push_is_not_configured_even_with_a_subscription(self, logged_client, db_session):
        me = logged_client.get("/api/v1/auth/me").json()
        db_session.add(
            PushSubscriptionModel(
                id=uuid4(),
                user_id=UUID(me["id"]),
                endpoint="https://fcm.googleapis.com/send/already-subscribed",
                p256dh="p",
                auth="a",
            )
        )
        db_session.commit()

        app.dependency_overrides[get_settings] = _settings_with_push_disabled
        try:
            response = logged_client.post("/api/v1/notifications/test")
        finally:
            del app.dependency_overrides[get_settings]

        assert response.status_code == 503
