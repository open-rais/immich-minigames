import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from conftest import mint_invite_code

from services.auth_service import UnauthorizedError


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


class TestAccessToken:
    def test_roundtrip_returns_the_same_user(self, auth_service):
        user = _register(auth_service)

        token = auth_service.create_access_token(user)
        resolved = auth_service.get_user_from_token(token)

        assert resolved.id == user.id

    def test_garbage_token_raises(self, auth_service):
        with pytest.raises(UnauthorizedError):
            auth_service.get_user_from_token("not-a-real-token")

    def test_expired_token_raises(self, auth_service):
        user = _register(auth_service)
        expired = jwt.encode(
            {"sub": str(user.id), "exp": 0},
            auth_service._settings.jwt_secret,
            algorithm="HS256",
        )

        with pytest.raises(UnauthorizedError):
            auth_service.get_user_from_token(expired)

    def test_token_for_unknown_user_id_raises(self, auth_service):
        token = jwt.encode(
            {"sub": str(uuid.uuid4())},
            auth_service._settings.jwt_secret,
            algorithm="HS256",
        )

        with pytest.raises(UnauthorizedError):
            auth_service.get_user_from_token(token)

    def test_token_issued_before_a_password_change_is_revoked(self, auth_service):
        # iat is built by hand with a few seconds of slack rather than via create_access_token()'s
        # "now" - JWT's iat/exp are integer-second NumericDates (RFC 7519), so a token minted and a
        # password changed within the same real-world second would truncate to equal timestamps and
        # not trigger the strict `<` rejection this test exists to check - flaky depending on
        # execution speed rather than a real bug. See get_user_from_token's own comment for why the
        # comparison is strict `<` in the first place (the re-issued-cookie-in-the-same-request case
        # needs iat == password_changed_at, truncated, to still pass).
        user = _register(auth_service)
        stale_token = jwt.encode(
            {
                "sub": str(user.id),
                "iat": datetime.now(UTC) - timedelta(seconds=5),
                "exp": datetime.now(UTC) + timedelta(days=1),
            },
            auth_service._settings.jwt_secret,
            algorithm="HS256",
        )

        auth_service.change_password(user, "correct-horse-battery-staple", "new-password-123")

        with pytest.raises(UnauthorizedError):
            auth_service.get_user_from_token(stale_token)

    def test_token_issued_after_a_password_change_is_accepted(self, auth_service):
        user = _register(auth_service)
        auth_service.change_password(user, "correct-horse-battery-staple", "new-password-123")

        token = auth_service.create_access_token(user)
        resolved = auth_service.get_user_from_token(token)

        assert resolved.id == user.id

    def test_token_without_an_iat_claim_is_not_revoked_by_a_password_change(self, auth_service):
        # Simulates a session that was already active when this code shipped - no `iat` to compare
        # against password_changed_at, so it must keep working rather than force a mass logout.
        user = _register(auth_service)
        token = jwt.encode(
            {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(days=1)},
            auth_service._settings.jwt_secret,
            algorithm="HS256",
        )

        auth_service.change_password(user, "correct-horse-battery-staple", "new-password-123")

        resolved = auth_service.get_user_from_token(token)
        assert resolved.id == user.id
