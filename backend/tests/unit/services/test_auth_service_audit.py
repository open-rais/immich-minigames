import uuid

import pytest
from conftest import mint_invite_code

from config import Settings
from services.auth_service import AuthService, InvalidCredentialsError
from services.invite_service import InvalidInviteError, InviteService


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(auth_service, **overrides):
    defaults = {
        "email": f"{_unique('user')}@example.com",
        "username": _unique("user"),
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
        "invite_code": mint_invite_code(),
    }
    defaults.update(overrides)
    return auth_service.register(**defaults)


class TestAuditEvents:
    """The catalog of events AuthService emits."""

    def test_register_emits_register_ok_with_via_invite(self, auth_service, audit_log):
        user = _register(auth_service)

        events = [r.event for r in audit_log.records]
        assert "register_ok" in events
        record = next(r for r in audit_log.records if r.event == "register_ok")
        assert record.user_id == str(user.id)
        assert record.email == user.email
        assert record.via == "invite"

    def test_register_without_an_invite_code_emits_register_rejected(self, auth_service, audit_log):
        with pytest.raises(InvalidInviteError):
            _register(auth_service, invite_code=None)

        record = next(r for r in audit_log.records if r.event == "register_rejected")
        assert record.reason == "an invite code is required to register"

    def test_register_with_an_unknown_invite_code_emits_register_rejected(self, auth_service, audit_log):
        with pytest.raises(InvalidInviteError):
            _register(auth_service, invite_code="not-a-real-code")

        record = next(r for r in audit_log.records if r.event == "register_rejected")
        assert record.reason == "invalid, used, or expired token"

    def test_bootstrap_registration_emits_register_ok_with_via_bootstrap_token(
        self, db_session, monkeypatch, audit_log
    ):
        settings = Settings(initial_invite_token="bootstrap-secret")
        service = AuthService(db_session, settings=settings)
        monkeypatch.setattr(service, "_is_first_user", lambda: True)

        _register(service, invite_code="bootstrap-secret")

        record = next(r for r in audit_log.records if r.event == "register_ok")
        assert record.via == "bootstrap_token"

    def test_bootstrap_wrong_token_emits_register_rejected(self, db_session, monkeypatch, audit_log):
        settings = Settings(initial_invite_token="bootstrap-secret")
        service = AuthService(db_session, settings=settings)
        monkeypatch.setattr(service, "_is_first_user", lambda: True)

        with pytest.raises(InvalidInviteError):
            _register(service, invite_code="wrong")

        record = next(r for r in audit_log.records if r.event == "register_rejected")
        assert record.reason == "invalid initial invite token"

    def test_free_first_registration_emits_register_ok_with_via_first_user(self, db_session, monkeypatch, audit_log):
        settings = Settings(initial_invite_token=None)
        service = AuthService(db_session, settings=settings)
        monkeypatch.setattr(service, "_is_first_user", lambda: True)

        _register(service, invite_code=None)

        record = next(r for r in audit_log.records if r.event == "register_ok")
        assert record.via == "first_user"

    def test_correct_login_emits_login_ok(self, auth_service, audit_log):
        user = _register(auth_service, password="correct-horse-battery-staple")
        audit_log.clear()

        auth_service.authenticate(user.email, "correct-horse-battery-staple")

        record = next(r for r in audit_log.records if r.event == "login_ok")
        assert record.email == user.email
        assert record.user_id == str(user.id)

    def test_wrong_password_emits_login_failed_with_user_id(self, auth_service, audit_log):
        user = _register(auth_service, password="correct-horse-battery-staple")
        audit_log.clear()

        with pytest.raises(InvalidCredentialsError):
            auth_service.authenticate(user.email, "wrong-password")

        record = next(r for r in audit_log.records if r.event == "login_failed")
        assert record.email == user.email
        assert record.user_id == str(user.id)

    def test_unknown_email_emits_login_failed_without_user_id(self, auth_service, audit_log):
        with pytest.raises(InvalidCredentialsError):
            auth_service.authenticate("nobody-audit@example.com", "whatever")

        record = next(r for r in audit_log.records if r.event == "login_failed")
        assert record.email == "nobody-audit@example.com"
        assert not hasattr(record, "user_id")

    def test_change_password_emits_password_change_ok(self, auth_service, audit_log):
        user = _register(auth_service, password="correct-horse-battery-staple")
        audit_log.clear()

        auth_service.change_password(user, "correct-horse-battery-staple", "new-password-123")

        record = next(r for r in audit_log.records if r.event == "password_change_ok")
        assert record.user_id == str(user.id)

    def test_wrong_current_password_emits_password_change_failed(self, auth_service, audit_log):
        user = _register(auth_service, password="correct-horse-battery-staple")
        audit_log.clear()

        with pytest.raises(InvalidCredentialsError):
            auth_service.change_password(user, "wrong-password", "new-password-123")

        record = next(r for r in audit_log.records if r.event == "password_change_failed")
        assert record.user_id == str(user.id)

    def test_reset_password_emits_password_reset_ok(self, auth_service, db_session, audit_log):
        user = _register(auth_service, password="correct-horse-battery-staple")
        token = InviteService(db_session).create_invite(kind="password_reset", user_id=user.id)[1]
        db_session.commit()
        audit_log.clear()

        auth_service.reset_password(token, "new-password-123")

        record = next(r for r in audit_log.records if r.event == "password_reset_ok")
        assert record.user_id == str(user.id)

    def test_unknown_reset_token_emits_password_reset_failed_without_the_token(self, auth_service, audit_log):
        with pytest.raises(InvalidInviteError):
            auth_service.reset_password("not-a-real-token", "new-password-123")

        record = next(r for r in audit_log.records if r.event == "password_reset_failed")
        assert "not-a-real-token" not in record.reason
        assert not hasattr(record, "token")

    def test_update_profile_emits_profile_updated_with_changed_field_names(self, auth_service, audit_log):
        user = _register(auth_service)
        audit_log.clear()

        auth_service.update_profile(user, username=_unique("renamed"), full_name="New Name")

        record = next(r for r in audit_log.records if r.event == "profile_updated")
        assert record.target_user_id == str(user.id)
        assert set(record.fields) == {"username", "full_name"}

    def test_update_profile_with_nothing_changed_emits_no_event(self, auth_service, audit_log):
        user = _register(auth_service)
        audit_log.clear()

        auth_service.update_profile(user, username=None, full_name=None)

        assert not any(r.event == "profile_updated" for r in audit_log.records)

    def test_set_skin_emits_skin_updated(self, auth_service, audit_log):
        user = _register(auth_service)
        audit_log.clear()

        auth_service.set_skin(user, uuid.uuid4())

        record = next(r for r in audit_log.records if r.event == "skin_updated")
        assert record.target_user_id == str(user.id)
        assert record.fields == ["skin_person_id"]
