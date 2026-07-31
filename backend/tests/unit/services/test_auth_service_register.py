import threading
import uuid

import pytest
from conftest import mint_invite_code

from config import Settings
from persistence.base import get_session_factory
from persistence.users import UserModel
from services.auth_service import AuthService, EmailAlreadyExistsError, UsernameAlreadyExistsError
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


class TestRegisterInvite:
    # auth_service (conftest.py) uses real get_settings() - by the time any of these run, other
    # tests have already registered users, so _is_first_user() is naturally False without needing
    # to monkeypatch it (unlike TestRegisterBootstrap below, which explicitly forces it True).

    def test_without_an_invite_code_raises(self, auth_service):
        with pytest.raises(InvalidInviteError):
            _register(auth_service, invite_code=None)

    def test_unknown_invite_code_raises(self, auth_service):
        with pytest.raises(InvalidInviteError):
            _register(auth_service, invite_code="not-a-real-code")

    def test_valid_invite_code_succeeds_and_burns_it(self, auth_service, db_session):
        code = InviteService(db_session).create_invite(kind="invite")[1]
        db_session.commit()

        user = _register(auth_service, invite_code=code)

        assert user.id is not None
        with pytest.raises(InvalidInviteError):
            _register(auth_service, invite_code=code)

    def test_a_failed_registration_does_not_burn_the_invite(self, auth_service, db_session):
        code = InviteService(db_session).create_invite(kind="invite")[1]
        db_session.commit()
        email = f"{_unique('dup')}@example.com"
        _register(auth_service, email=email)  # takes the email with a different (fresh) invite

        with pytest.raises(EmailAlreadyExistsError):
            _register(auth_service, email=email, invite_code=code)

        # The invite from the failed attempt above is still good.
        user = _register(auth_service, invite_code=code)
        assert user.id is not None


class TestRegisterBootstrap:
    # _is_first_user() is monkeypatched to True throughout - the shared test DB is never actually
    # empty by the time these run (other tests register users first), so this is the only way to
    # exercise the bootstrap branch deterministically (see conftest.py's mint_invite_code
    # docstring for the same concern from the other direction).

    def test_matching_initial_token_succeeds(self, db_session, monkeypatch):
        settings = Settings(initial_invite_token="bootstrap-secret")
        service = AuthService(db_session, settings=settings)
        monkeypatch.setattr(service, "_is_first_user", lambda: True)

        user = _register(service, invite_code="bootstrap-secret")

        assert user.id is not None

    def test_wrong_initial_token_raises(self, db_session, monkeypatch):
        settings = Settings(initial_invite_token="bootstrap-secret")
        service = AuthService(db_session, settings=settings)
        monkeypatch.setattr(service, "_is_first_user", lambda: True)

        with pytest.raises(InvalidInviteError):
            _register(service, invite_code="wrong")

    def test_missing_invite_code_with_a_configured_token_raises(self, db_session, monkeypatch):
        settings = Settings(initial_invite_token="bootstrap-secret")
        service = AuthService(db_session, settings=settings)
        monkeypatch.setattr(service, "_is_first_user", lambda: True)

        with pytest.raises(InvalidInviteError):
            _register(service, invite_code=None)

    def test_unset_initial_token_allows_free_registration(self, db_session, monkeypatch):
        settings = Settings(initial_invite_token=None)
        service = AuthService(db_session, settings=settings)
        monkeypatch.setattr(service, "_is_first_user", lambda: True)

        user = _register(service, invite_code=None)

        assert user.id is not None

    def test_blank_initial_token_also_allows_free_registration(self, db_session, monkeypatch):
        # "" (not None) is exactly what INITIAL_INVITE_TOKEN parses to whenever
        # it's left blank rather than fully absent: .env.example's own documented default
        # (`INITIAL_INVITE_TOKEN=`) and Docker Compose's `${INITIAL_INVITE_TOKEN}` interpolation
        # with no var defined (verified via `docker compose config`) both produce "", never None.
        # Must behave exactly like None (free first registration), not like a configured token
        # nothing could ever match.
        settings = Settings(initial_invite_token="")
        service = AuthService(db_session, settings=settings)
        monkeypatch.setattr(service, "_is_first_user", lambda: True)

        user = _register(service, invite_code=None)

        assert user.id is not None


class TestRegisterConcurrency:
    def test_losing_a_registration_race_raises_the_typed_error(self, db_session):
        # Two registrations for the same email can both pass the
        # pre-check before either commits. Reproduced deterministically (not sleep-and-hope):
        # Postgres blocks a second INSERT against an uncommitted-but-conflicting unique value until
        # the first transaction resolves, then re-checks - so holding "A"'s insert open reliably
        # makes "B"'s real register() call block, then fail for real once "A" commits.
        email = f"{_unique('race')}@example.com"
        db_session.add(UserModel(email=email, username=_unique("race-a"), full_name="A", password_hash="irrelevant"))
        # add() alone only stages the object in the Session - flush() is what actually sends the
        # INSERT to Postgres (uncommitted), which is what makes "B"'s conflicting insert block below.
        db_session.flush()

        session_b = get_session_factory()()
        try:
            service_b = AuthService(session_b)
            b_result = {}

            def run_b():
                try:
                    service_b.register(
                        email=email,
                        username=_unique("race-b"),
                        full_name="B",
                        password="pw",
                        invite_code=mint_invite_code(),
                    )
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
