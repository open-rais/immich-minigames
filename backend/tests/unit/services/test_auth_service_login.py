import uuid

import pytest
from conftest import mint_invite_code

from services.auth_service import InvalidCredentialsError


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


class TestAuthenticate:
    def test_correct_password_returns_the_user(self, auth_service):
        user = _register(auth_service, password="correct-horse-battery-staple")

        authenticated = auth_service.authenticate(user.email, "correct-horse-battery-staple")

        assert authenticated.id == user.id

    def test_wrong_password_raises(self, auth_service):
        user = _register(auth_service, password="correct-horse-battery-staple")

        with pytest.raises(InvalidCredentialsError):
            auth_service.authenticate(user.email, "wrong-password")

    def test_unknown_email_raises(self, auth_service):
        with pytest.raises(InvalidCredentialsError):
            auth_service.authenticate("nobody@example.com", "whatever")
