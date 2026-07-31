import threading
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from conftest import mint_invite_code

from config import Settings
from persistence.base import get_session_factory
from persistence.users import UserModel
from services.auth_service import (
    AuthService,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UnauthorizedError,
    UsernameAlreadyExistsError,
)
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
