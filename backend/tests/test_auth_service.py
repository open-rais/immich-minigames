import uuid

import jwt
import pytest

from services.auth_service import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UnauthorizedError,
    UsernameAlreadyExistsError,
)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(auth_service, **overrides):
    defaults = {
        "email": f"{_unique('user')}@example.com",
        "username": _unique("user"),
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
    }
    defaults.update(overrides)
    return auth_service.register(**defaults)


class TestRegister:
    def test_persists_the_user_with_a_hashed_password(self, auth_service):
        user = _register(auth_service, password="my-secret-password")

        assert user.id is not None
        assert user.password_hash != "my-secret-password"

    def test_duplicate_email_raises(self, auth_service):
        email = f"{_unique('dup')}@example.com"
        _register(auth_service, email=email)

        with pytest.raises(EmailAlreadyExistsError):
            _register(auth_service, email=email)

    def test_duplicate_username_raises(self, auth_service):
        username = _unique("dupuser")
        _register(auth_service, username=username)

        with pytest.raises(UsernameAlreadyExistsError):
            _register(auth_service, username=username)


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


class TestUpdateProfile:
    def test_updates_username_and_full_name(self, auth_service):
        user = _register(auth_service)
        new_username = _unique("newname")

        updated = auth_service.update_profile(user, username=new_username, full_name="New Name")

        assert updated.username == new_username
        assert updated.full_name == "New Name"

    def test_omitted_fields_are_left_unchanged(self, auth_service):
        user = _register(auth_service, full_name="Original Name")
        original_username = user.username

        updated = auth_service.update_profile(user, username=None, full_name=None)

        assert updated.username == original_username
        assert updated.full_name == "Original Name"

    def test_taking_someone_elses_username_raises(self, auth_service):
        other = _register(auth_service)
        user = _register(auth_service)

        with pytest.raises(UsernameAlreadyExistsError):
            auth_service.update_profile(user, username=other.username)

    def test_keeping_own_current_username_does_not_raise(self, auth_service):
        user = _register(auth_service)

        updated = auth_service.update_profile(user, username=user.username, full_name="Same Name")

        assert updated.username == user.username


class TestSetSkin:
    def test_sets_the_skin_person_id(self, auth_service):
        user = _register(auth_service)
        person_id = uuid.uuid4()

        updated = auth_service.set_skin(user, person_id)

        assert updated.skin_person_id == person_id

    def test_none_clears_the_skin(self, auth_service):
        user = _register(auth_service)
        auth_service.set_skin(user, uuid.uuid4())

        updated = auth_service.set_skin(user, None)

        assert updated.skin_person_id is None
