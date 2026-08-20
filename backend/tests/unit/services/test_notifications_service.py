import uuid
from dataclasses import dataclass

import pytest
from conftest import mint_invite_code

import services.notifications as notifications_module
from config import Settings
from persistence.notifications import NotificationPreferencesModel, PushSubscriptionModel
from services.notifications import (
    NoPushSubscriptionsError,
    NotificationPreferences,
    NotificationService,
    PushSendFailedError,
)
from services.notifications.endpoint_safety import PushEndpointRejectedError

_ENDPOINT = "https://fcm.googleapis.com/send/abc"


@dataclass
class _FakePushResult:
    ok: bool
    should_delete_subscription: bool
    status_code: int | None = None


def _register_user(auth_service):
    unique = uuid.uuid4().hex[:8]
    return auth_service.register(
        email=f"push-{unique}@example.com",
        username=f"push-{unique}",
        full_name="Push Test User",
        password="correct-horse-battery-staple",
        invite_code=mint_invite_code(),
    )


def _push_enabled_settings() -> Settings:
    return Settings(
        vapid_public_key="public-key",
        vapid_private_key="private-key",
        vapid_contact_email="owner@example.com",
    )


@pytest.fixture
def user(auth_service):
    return _register_user(auth_service)


@pytest.fixture
def notifications_service(db_session):
    return NotificationService(db_session, _push_enabled_settings())


class TestPreferences:
    def test_get_preferences_defaults_to_everything_off_without_creating_a_row(
        self, notifications_service, db_session, user
    ):
        prefs = notifications_service.get_preferences(user.id)
        assert prefs == NotificationPreferences(
            daily_reminders=False, birthdays=False, album_anniversary=False, language="en"
        )
        assert db_session.get(NotificationPreferencesModel, user.id) is None

    def test_update_preferences_creates_then_updates_the_same_row(self, notifications_service, user):
        notifications_service.update_preferences(
            user.id,
            NotificationPreferences(daily_reminders=True, birthdays=False, album_anniversary=False, language="es"),
        )
        first = notifications_service.get_preferences(user.id)
        assert first.daily_reminders is True
        assert first.language == "es"

        notifications_service.update_preferences(
            user.id,
            NotificationPreferences(daily_reminders=False, birthdays=True, album_anniversary=True, language="en"),
        )
        second = notifications_service.get_preferences(user.id)
        assert second == NotificationPreferences(
            daily_reminders=False, birthdays=True, album_anniversary=True, language="en"
        )


class TestSubscriptions:
    def test_add_subscription_rejects_a_non_allowlisted_endpoint(self, notifications_service, user):
        with pytest.raises(PushEndpointRejectedError):
            notifications_service.add_subscription(user.id, "https://evil.example.com/send/abc", "p", "a")

    def test_add_subscription_is_idempotent_by_endpoint(self, notifications_service, user, db_session):
        notifications_service.add_subscription(user.id, _ENDPOINT, "p256dh-1", "auth-1")
        notifications_service.add_subscription(user.id, _ENDPOINT, "p256dh-2", "auth-2")

        rows = list(
            db_session.query(PushSubscriptionModel).filter(PushSubscriptionModel.endpoint == _ENDPOINT).all()
        )
        assert len(rows) == 1
        assert rows[0].p256dh == "p256dh-2"

    def test_remove_subscription_is_scoped_to_the_owning_user(
        self, notifications_service, user, auth_service, db_session
    ):
        other_user = _register_user(auth_service)
        notifications_service.add_subscription(user.id, _ENDPOINT, "p", "a")

        notifications_service.remove_subscription(other_user.id, _ENDPOINT)
        assert db_session.query(PushSubscriptionModel).filter(PushSubscriptionModel.endpoint == _ENDPOINT).first()

        notifications_service.remove_subscription(user.id, _ENDPOINT)
        assert not db_session.query(PushSubscriptionModel).filter(PushSubscriptionModel.endpoint == _ENDPOINT).first()


class TestSendTest:
    def test_raises_when_the_account_has_no_subscriptions(self, notifications_service, user):
        with pytest.raises(NoPushSubscriptionsError):
            notifications_service.send_test(user.id)

    def test_a_successful_send_updates_last_success_at_and_resets_failure_count(
        self, notifications_service, user, db_session, monkeypatch
    ):
        notifications_service.add_subscription(user.id, _ENDPOINT, "p", "a")
        monkeypatch.setattr(
            notifications_module,
            "send_push",
            lambda *a, **k: _FakePushResult(ok=True, should_delete_subscription=False),
        )

        notifications_service.send_test(user.id)

        row = db_session.query(PushSubscriptionModel).filter(PushSubscriptionModel.endpoint == _ENDPOINT).one()
        assert row.last_success_at is not None
        assert row.failure_count == 0

    def test_a_410_deletes_the_subscription(self, notifications_service, user, db_session, monkeypatch):
        notifications_service.add_subscription(user.id, _ENDPOINT, "p", "a")
        monkeypatch.setattr(
            notifications_module,
            "send_push",
            lambda *a, **k: _FakePushResult(ok=False, should_delete_subscription=True, status_code=410),
        )

        with pytest.raises(PushSendFailedError):
            notifications_service.send_test(user.id)

        assert not db_session.query(PushSubscriptionModel).filter(PushSubscriptionModel.endpoint == _ENDPOINT).first()

    def test_a_transient_failure_increments_failure_count_without_deleting(
        self, notifications_service, user, db_session, monkeypatch
    ):
        notifications_service.add_subscription(user.id, _ENDPOINT, "p", "a")
        monkeypatch.setattr(
            notifications_module,
            "send_push",
            lambda *a, **k: _FakePushResult(ok=False, should_delete_subscription=False, status_code=503),
        )

        with pytest.raises(PushSendFailedError):
            notifications_service.send_test(user.id)

        row = db_session.query(PushSubscriptionModel).filter(PushSubscriptionModel.endpoint == _ENDPOINT).one()
        assert row.failure_count == 1

    def test_one_success_among_several_does_not_raise(self, notifications_service, user, db_session, monkeypatch):
        other_endpoint = "https://fcm.googleapis.com/send/other"
        notifications_service.add_subscription(user.id, _ENDPOINT, "p", "a")
        notifications_service.add_subscription(user.id, other_endpoint, "p", "a")

        def _fake_send_push(*args, **kwargs):
            if kwargs["endpoint"] == _ENDPOINT:
                return _FakePushResult(ok=True, should_delete_subscription=False)
            return _FakePushResult(ok=False, should_delete_subscription=False, status_code=503)

        monkeypatch.setattr(notifications_module, "send_push", _fake_send_push)

        notifications_service.send_test(user.id)  # must not raise

        failed_row = (
            db_session.query(PushSubscriptionModel).filter(PushSubscriptionModel.endpoint == other_endpoint).one()
        )
        assert failed_row.failure_count == 1
