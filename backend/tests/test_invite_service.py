import threading
import uuid
from datetime import timedelta

import pytest

from persistence.base import get_session_factory
from persistence.users import UserModel
from services.invite_service import InvalidInviteError, InviteNotFoundError, InviteService


def _unique_kind() -> str:
    # Isolates each test's invites from every other test's (list_invites filters by kind, and the
    # shared DB is never reset between tests - see conftest.py) without needing a per-test DB
    # transaction rollback this suite doesn't have.
    return f"invite-{uuid.uuid4().hex[:8]}"


class TestCreateAndConsume:
    def test_consume_with_the_right_token_and_kind_succeeds(self, db_session):
        service = InviteService(db_session)
        kind = _unique_kind()
        invite, token = service.create_invite(kind=kind)

        consumed = service.consume_invite(token, kind=kind)

        assert consumed.id == invite.id
        db_session.commit()

    def test_second_consume_of_the_same_token_raises(self, db_session):
        service = InviteService(db_session)
        kind = _unique_kind()
        _, token = service.create_invite(kind=kind)
        service.consume_invite(token, kind=kind)
        db_session.commit()

        with pytest.raises(InvalidInviteError):
            service.consume_invite(token, kind=kind)

    def test_wrong_kind_raises(self, db_session):
        service = InviteService(db_session)
        kind = _unique_kind()
        _, token = service.create_invite(kind=kind)

        with pytest.raises(InvalidInviteError):
            service.consume_invite(token, kind=f"{kind}-other")

    def test_unknown_token_raises(self, db_session):
        service = InviteService(db_session)

        with pytest.raises(InvalidInviteError):
            service.consume_invite("not-a-real-token", kind=_unique_kind())

    def test_expired_token_raises(self, db_session):
        service = InviteService(db_session)
        kind = _unique_kind()
        _, token = service.create_invite(kind=kind, ttl=timedelta(seconds=-1))

        with pytest.raises(InvalidInviteError):
            service.consume_invite(token, kind=kind)

    def test_consume_does_not_commit_by_itself(self, db_session):
        # AuthService.register (and F2's reset-password) rely on this: consume_invite only
        # flushes, so a rollback after it (e.g. a duplicate email) undoes the consumption too.
        service = InviteService(db_session)
        kind = _unique_kind()
        _, token = service.create_invite(kind=kind)

        service.consume_invite(token, kind=kind)
        db_session.rollback()

        # Un-rolled-back: consuming again should succeed, since the UPDATE never committed.
        consumed_again = service.consume_invite(token, kind=kind)
        assert consumed_again is not None
        db_session.commit()


class TestConsumeConcurrency:
    def test_only_one_of_two_racing_consumers_wins(self, db_session):
        # Mirrors test_auth_service.py's TestRegisterConcurrency technique: hold one consumer's
        # UPDATE open (uncommitted) so the second's conflicting UPDATE reliably blocks on it, then
        # resolve - deterministic, not a sleep-and-hope race.
        service_a = InviteService(db_session)
        kind = _unique_kind()
        _, token = service_a.create_invite(kind=kind)

        session_b = get_session_factory()()
        try:
            service_b = InviteService(session_b)
            b_result = {}

            service_a.consume_invite(token, kind=kind)  # flushed, uncommitted

            def run_b():
                try:
                    b_result["invite"] = service_b.consume_invite(token, kind=kind)
                except Exception as exc:
                    b_result["error"] = exc

            t = threading.Thread(target=run_b)
            t.start()
            t.join(timeout=0.3)
            assert not b_result  # blocked on "A"'s uncommitted UPDATE of the same row

            db_session.commit()  # "A" wins the race
            t.join(timeout=2)
        finally:
            session_b.close()

        assert isinstance(b_result.get("error"), InvalidInviteError)


class TestListInvites:
    def test_filters_by_kind_and_orders_newest_first(self, db_session):
        service = InviteService(db_session)
        kind = _unique_kind()
        first, _ = service.create_invite(kind=kind)
        second, _ = service.create_invite(kind=kind)
        service.create_invite(kind=f"{kind}-other")

        invites = service.list_invites(kind=kind)

        assert [i.id for i in invites] == [second.id, first.id]


class TestRevokeInvite:
    def test_revoking_a_pending_invite_blocks_future_consumption(self, db_session):
        service = InviteService(db_session)
        kind = _unique_kind()
        invite, token = service.create_invite(kind=kind)

        service.revoke_invite(invite.id)

        with pytest.raises(InvalidInviteError):
            service.consume_invite(token, kind=kind)

    def test_revoking_an_unknown_id_raises(self, db_session):
        service = InviteService(db_session)

        with pytest.raises(InviteNotFoundError):
            service.revoke_invite(uuid.uuid4())

    def test_revoking_an_already_used_invite_raises(self, db_session):
        service = InviteService(db_session)
        kind = _unique_kind()
        invite, token = service.create_invite(kind=kind)
        service.consume_invite(token, kind=kind)
        db_session.commit()

        with pytest.raises(InviteNotFoundError):
            service.revoke_invite(invite.id)


class TestAuditEvents:
    """docs/TODO/LOGGING.md §4.4, phase F2."""

    def test_create_invite_emits_invite_created_for_either_kind(self, db_session, audit_log):
        service = InviteService(db_session)

        invite, _ = service.create_invite(kind="invite")

        record = next(r for r in audit_log.records if r.event == "invite_created")
        assert record.invite_id == str(invite.id)
        assert record.kind == "invite"
        assert record.expires_at == invite.expires_at.isoformat()

    def test_create_invite_emits_invite_created_for_password_reset_too(self, db_session, audit_log):
        user = UserModel(
            email=f"invite-audit-{uuid.uuid4().hex[:8]}@example.com",
            username=f"invite-audit-{uuid.uuid4().hex[:8]}",
            full_name="Invite Audit Target",
            password_hash="irrelevant",
        )
        db_session.add(user)
        db_session.commit()
        service = InviteService(db_session)

        invite, _ = service.create_invite(kind="password_reset", user_id=user.id)

        record = next(r for r in audit_log.records if r.event == "invite_created")
        assert record.kind == "password_reset"

    def test_revoke_invite_emits_invite_revoked(self, db_session, audit_log):
        service = InviteService(db_session)
        kind = _unique_kind()
        invite, _ = service.create_invite(kind=kind)
        audit_log.clear()

        service.revoke_invite(invite.id)

        record = next(r for r in audit_log.records if r.event == "invite_revoked")
        assert record.invite_id == str(invite.id)
        assert record.kind == kind
