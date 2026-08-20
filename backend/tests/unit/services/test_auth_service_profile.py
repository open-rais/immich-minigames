import threading
import uuid

import pytest
from conftest import mint_invite_code

from persistence.base import get_session_factory
from persistence.users import UserModel
from services.auth_service import AuthService, UsernameAlreadyExistsError


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


class TestUsernamesFor:
    def test_resolves_multiple_ids_in_one_call(self, auth_service):
        alice = _register(auth_service)
        bob = _register(auth_service)

        usernames = auth_service.usernames_for([alice.id, bob.id])

        assert usernames == {alice.id: alice.username, bob.id: bob.username}

    def test_unknown_id_is_simply_absent(self, auth_service):
        usernames = auth_service.usernames_for([uuid.uuid4()])

        assert usernames == {}


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
