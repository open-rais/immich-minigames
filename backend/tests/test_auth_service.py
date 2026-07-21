import threading
import uuid

import jwt
import pytest

from persistence.base import get_session_factory
from persistence.users import UserModel
from services.auth_service import (
    AuthService,
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


class TestRegisterConcurrency:
    def test_losing_a_registration_race_raises_the_typed_error(self, db_session):
        # docs/TODO/CODE-REVIEW.md #8: two registrations for the same email can both pass the
        # pre-check before either commits. Reproduced deterministically (not sleep-and-hope):
        # Postgres blocks a second INSERT against an uncommitted-but-conflicting unique value until
        # the first transaction resolves, then re-checks - so holding "A"'s insert open reliably
        # makes "B"'s real register() call block, then fail for real once "A" commits.
        email = f"{_unique('race')}@example.com"
        db_session.add(
            UserModel(email=email, username=_unique("race-a"), full_name="A", password_hash="irrelevant")
        )
        # add() alone only stages the object in the Session - flush() is what actually sends the
        # INSERT to Postgres (uncommitted), which is what makes "B"'s conflicting insert block below.
        db_session.flush()

        session_b = get_session_factory()()
        try:
            service_b = AuthService(session_b)
            b_result = {}

            def run_b():
                try:
                    service_b.register(email=email, username=_unique("race-b"), full_name="B", password="pw")
                except Exception as exc:
                    b_result["error"] = exc

            t = threading.Thread(target=run_b)
            t.start()
            t.join(timeout=0.3)
            assert not b_result  # blocked on "A"'s uncommitted insert of the same email

            db_session.commit()  # "A" wins the race
            t.join(timeout=2)
        finally:
            session_b.close()

        assert isinstance(b_result.get("error"), EmailAlreadyExistsError)


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


class TestUpdateProfileConcurrency:
    def test_losing_a_username_race_raises_the_typed_error(self, auth_service, db_session):
        # Same race as TestRegisterConcurrency, but for update_profile's username uniqueness - two
        # already-registered accounts both try to rename to the same username at once.
        alice = _register(auth_service)
        bob = _register(auth_service)
        contested = _unique("contested")

        # "A": the same UPDATE update_profile would do, left uncommitted. flush() sends it to
        # Postgres now (not just staged in the Session) - that's what makes "B"'s conflicting
        # update block below.
        alice_row = db_session.get(UserModel, alice.id)
        alice_row.username = contested
        db_session.flush()

        session_b = get_session_factory()()
        try:
            service_b = AuthService(session_b)
            bob_in_session_b = session_b.get(UserModel, bob.id)
            b_result = {}

            def run_b():
                try:
                    service_b.update_profile(bob_in_session_b, username=contested)
                except Exception as exc:
                    b_result["error"] = exc

            t = threading.Thread(target=run_b)
            t.start()
            t.join(timeout=0.3)
            assert not b_result  # blocked on "A"'s uncommitted rename to the same username

            db_session.commit()  # "A" wins the race
            t.join(timeout=2)
        finally:
            session_b.close()

        assert isinstance(b_result.get("error"), UsernameAlreadyExistsError)


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
