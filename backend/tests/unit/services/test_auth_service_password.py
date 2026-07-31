import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from conftest import mint_invite_code

from services.auth_service import InvalidCredentialsError, UnauthorizedError
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


class TestChangePassword:
    def test_wrong_current_password_raises(self, auth_service):
        user = _register(auth_service, password="correct-horse-battery-staple")

        with pytest.raises(InvalidCredentialsError):
            auth_service.change_password(user, "wrong-password", "new-password-123")

    def test_correct_current_password_updates_the_hash_and_timestamp(self, auth_service):
        user = _register(auth_service, password="correct-horse-battery-staple")
        assert user.password_changed_at is None
        old_hash = user.password_hash

        updated = auth_service.change_password(user, "correct-horse-battery-staple", "new-password-123")

        assert updated.password_hash != old_hash
        assert updated.password_changed_at is not None
        assert auth_service.authenticate(user.email, "new-password-123").id == user.id


class TestResetPassword:
    def test_unknown_token_raises(self, auth_service):
        with pytest.raises(InvalidInviteError):
            auth_service.reset_password("not-a-real-token", "new-password-123")

    def test_an_invite_kind_token_does_not_work_for_reset(self, auth_service, db_session):
        # consume_invite is kind-scoped (services/invite_service.py) - a registration invite must
        # not double as a password-reset token.
        code = InviteService(db_session).create_invite(kind="invite")[1]
        db_session.commit()

        with pytest.raises(InvalidInviteError):
            auth_service.reset_password(code, "new-password-123")

    def test_valid_token_updates_the_password_and_authenticates(self, auth_service, db_session):
        user = _register(auth_service, password="correct-horse-battery-staple")
        token = InviteService(db_session).create_invite(kind="password_reset", user_id=user.id)[1]
        db_session.commit()
        old_hash = user.password_hash

        updated = auth_service.reset_password(token, "new-password-123")

        assert updated.id == user.id
        assert updated.password_hash != old_hash
        assert updated.password_changed_at is not None
        assert auth_service.authenticate(user.email, "new-password-123").id == user.id

    def test_reusing_the_same_token_raises(self, auth_service, db_session):
        user = _register(auth_service, password="correct-horse-battery-staple")
        token = InviteService(db_session).create_invite(kind="password_reset", user_id=user.id)[1]
        db_session.commit()
        auth_service.reset_password(token, "new-password-123")

        with pytest.raises(InvalidInviteError):
            auth_service.reset_password(token, "another-password-456")

    def test_only_affects_the_targeted_user(self, auth_service, db_session):
        target = _register(auth_service, password="correct-horse-battery-staple")
        other = _register(auth_service, password="correct-horse-battery-staple")
        token = InviteService(db_session).create_invite(kind="password_reset", user_id=target.id)[1]
        db_session.commit()

        auth_service.reset_password(token, "new-password-123")

        assert auth_service.authenticate(other.email, "correct-horse-battery-staple").id == other.id

    def test_revokes_a_session_issued_before_the_reset(self, auth_service, db_session):
        user = _register(auth_service, password="correct-horse-battery-staple")
        stale_token = jwt.encode(
            {
                "sub": str(user.id),
                "iat": datetime.now(UTC) - timedelta(seconds=5),
                "exp": datetime.now(UTC) + timedelta(days=1),
            },
            auth_service._settings.jwt_secret,
            algorithm="HS256",
        )
        reset_token = InviteService(db_session).create_invite(kind="password_reset", user_id=user.id)[1]
        db_session.commit()

        auth_service.reset_password(reset_token, "new-password-123")

        with pytest.raises(UnauthorizedError):
            auth_service.get_user_from_token(stale_token)
