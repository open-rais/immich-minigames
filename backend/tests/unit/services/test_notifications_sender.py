from dataclasses import dataclass

import pytest
import requests
from pywebpush import WebPushException

from config import Settings
from services.notifications import sender
from services.notifications.sender import PushNotConfiguredError, send_push


@dataclass
class _FakeResponse:
    status_code: int


def _push_enabled_settings() -> Settings:
    return Settings(
        vapid_public_key="public-key",
        vapid_private_key="private-key",
        vapid_contact_email="owner@example.com",
    )


def _send(**overrides):
    kwargs = {
        "settings": _push_enabled_settings(),
        "endpoint": "https://fcm.googleapis.com/send/abc",
        "p256dh": "p256dh-value",
        "auth": "auth-value",
        "title": "Title",
        "body": "Body",
        "url": "/",
        "tag": "test",
    }
    kwargs.update(overrides)
    return send_push(**kwargs)


class TestSendPush:
    def test_raises_when_push_is_not_configured(self):
        with pytest.raises(PushNotConfiguredError):
            send_push(
                # Explicitly nulled, not a bare Settings() - this must hold regardless of whether
                # the machine running this test happens to have real VAPID_* set in its own .env.
                Settings(vapid_public_key=None, vapid_private_key=None, vapid_contact_email=None),
                endpoint="https://fcm.googleapis.com/send/abc",
                p256dh="p",
                auth="a",
                title="t",
                body="b",
                url="/",
                tag="test",
            )

    def test_returns_ok_on_success(self, monkeypatch):
        monkeypatch.setattr(sender, "webpush", lambda **kwargs: _FakeResponse(status_code=201))
        result = _send()
        assert result.ok is True
        assert result.should_delete_subscription is False

    def test_a_410_gone_marks_the_subscription_for_deletion(self, monkeypatch):
        def _raise(**kwargs):
            raise WebPushException("gone", response=_FakeResponse(status_code=410))

        monkeypatch.setattr(sender, "webpush", _raise)
        result = _send()
        assert result.ok is False
        assert result.should_delete_subscription is True
        assert result.status_code == 410

    def test_a_404_not_found_marks_the_subscription_for_deletion(self, monkeypatch):
        def _raise(**kwargs):
            raise WebPushException("not found", response=_FakeResponse(status_code=404))

        monkeypatch.setattr(sender, "webpush", _raise)
        result = _send()
        assert result.should_delete_subscription is True

    def test_a_503_does_not_mark_the_subscription_for_deletion(self, monkeypatch):
        def _raise(**kwargs):
            raise WebPushException("unavailable", response=_FakeResponse(status_code=503))

        monkeypatch.setattr(sender, "webpush", _raise)
        result = _send()
        assert result.ok is False
        assert result.should_delete_subscription is False
        assert result.status_code == 503

    def test_a_429_does_not_mark_the_subscription_for_deletion(self, monkeypatch):
        def _raise(**kwargs):
            raise WebPushException("rate limited", response=_FakeResponse(status_code=429))

        monkeypatch.setattr(sender, "webpush", _raise)
        result = _send()
        assert result.should_delete_subscription is False


class TestNoRedirectSession:
    def test_forces_allow_redirects_false_by_default(self, monkeypatch):
        captured = {}

        def _fake_request(self, method, url, **kwargs):
            captured.update(kwargs)
            return _FakeResponse(status_code=200)

        monkeypatch.setattr(requests.Session, "request", _fake_request)
        session = sender._NoRedirectSession()
        session.post("https://fcm.googleapis.com/send/abc")

        assert captured["allow_redirects"] is False

    def test_does_not_override_an_explicit_allow_redirects(self, monkeypatch):
        captured = {}

        def _fake_request(self, method, url, **kwargs):
            captured.update(kwargs)
            return _FakeResponse(status_code=200)

        monkeypatch.setattr(requests.Session, "request", _fake_request)
        session = sender._NoRedirectSession()
        session.post("https://fcm.googleapis.com/send/abc", allow_redirects=True)

        assert captured["allow_redirects"] is True
