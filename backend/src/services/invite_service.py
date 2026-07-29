"""Invitations and admin-initiated password resets (roadmap #H, F1/F2) - one table
(persistence/invites.py's InviteModel), `kind` distinguishes the two ('invite' |
'password_reset'). Registration invites are admin-generated, single-use, expiring tokens; the
plain token is only ever available at creation time - only its SHA-256 hash is persisted
(high-entropy, app-generated, no dictionary attack possible, so no salt needed)."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from persistence.invites import InviteModel

_DEFAULT_TTL = timedelta(days=7)


class InvalidInviteError(Exception):
    pass


class InviteNotFoundError(Exception):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class InviteService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_invite(
        self, kind: str, user_id: UUID | None = None, ttl: timedelta = _DEFAULT_TTL
    ) -> tuple[InviteModel, str]:
        """Returns the persisted row and the plain token - the only place that plain value is ever
        available. The caller shows it to the admin once; it can't be recovered afterward."""
        token = secrets.token_urlsafe(32)
        invite = InviteModel(
            token_hash=_hash_token(token),
            kind=kind,
            user_id=user_id,
            expires_at=datetime.now(UTC) + ttl,
        )
        self._session.add(invite)
        self._session.commit()
        return invite, token

    def consume_invite(self, token: str, kind: str) -> InviteModel:
        """Single atomic UPDATE...RETURNING, no read-then-write window a concurrent consumer could
        slip through. Deliberately only flushes, never commits - the caller (AuthService.register,
        and F2's reset-password) does its own write in the same transaction, so a failure there
        (e.g. a duplicate email) rolls this back too instead of burning the invite for nothing."""
        stmt = (
            sa.update(InviteModel)
            .where(
                InviteModel.token_hash == _hash_token(token),
                InviteModel.kind == kind,
                InviteModel.used_at.is_(None),
                InviteModel.expires_at > sa.func.now(),
            )
            .values(used_at=sa.func.now())
            .returning(InviteModel.id)
        )
        invite_id = self._session.execute(stmt).scalar_one_or_none()
        if invite_id is None:
            # Deliberately one message for missing/already-used/expired - same anti-enumeration
            # reasoning as AuthService.authenticate's InvalidCredentialsError.
            raise InvalidInviteError("invalid, used, or expired invite code")
        self._session.flush()
        return self._session.get(InviteModel, invite_id)

    def list_invites(self, kind: str) -> list[InviteModel]:
        return list(
            self._session.scalars(
                sa.select(InviteModel).where(InviteModel.kind == kind).order_by(InviteModel.created_at.desc())
            )
        )

    def revoke_invite(self, invite_id: UUID) -> None:
        """Deletes a still-pending invite outright - an already-used one isn't revocable (it did
        its job; deleting it would erase admin-visible history for no benefit)."""
        invite = self._session.get(InviteModel, invite_id)
        if invite is None or invite.used_at is not None:
            raise InviteNotFoundError(f"invite {invite_id} not found or already used")
        self._session.delete(invite)
        self._session.commit()
