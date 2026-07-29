"""
Auth service - registers/authenticates this app's own user accounts (roadmap point B) and
issues/verifies their login JWT. Entirely separate from Immich's own users (never touches
Immich's Postgres schema). Games created while authenticated get GameModel.user_id set (roadmap
point E, see games_service.py) alongside the anonymous X-Owner-Id, which anonymous play still uses
on its own - full leaderboards are a later roadmap point (F).

Session model: stateless JWT in an httpOnly cookie, no server-side session table - "logout" just
clears the cookie client-side, a token copied before logout stays valid until it expires
(JWT_EXPIRE_DAYS). Accepted tradeoff for "lo básico" (see docs/TODO/ROADMAP.md point B) - revisit
if real revocation is ever needed.
"""

import secrets
from calendar import timegm
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import Settings, get_settings
from persistence.users import UserModel
from services.invite_service import InvalidInviteError, InviteService

_JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()


class EmailAlreadyExistsError(Exception):
    pass


class UsernameAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


class AuthService:
    def __init__(
        self, session: Session, settings: Settings | None = None, invite_service: InviteService | None = None
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._invite_service = invite_service or InviteService(session)

    def list_users(self, *, offset: int = 0, limit: int = 5) -> list[UserModel]:
        """Admin feature (ADMIN-FEATURE.md point #3) - newest-registered first, paginated (roadmap
        infinite-scroll UI, see api/admin_api.py) - offset/limit, same convention as
        ImmichService.search_persons."""
        stmt = select(UserModel).order_by(UserModel.created_at.desc()).offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def get_user_by_id(self, user_id: UUID) -> UserModel | None:
        """Admin feature (ADMIN-FEATURE.md point #3) - looks up any account by id, not just the
        caller's own (unlike get_user_from_token, which is JWT-subject-bound)."""
        return self._session.get(UserModel, user_id)

    def _is_first_user(self) -> bool:
        return self._session.scalar(select(UserModel.id).limit(1)) is None

    def _authorize_registration(self, invite_code: str | None) -> None:
        """Roadmap #H, F1 - registration is invite-only, except for the very first account (which
        can't have an invite yet - decision [H]). Raises InvalidInviteError, never returns a
        reason - same anti-enumeration shape as InviteService.consume_invite."""
        if self._is_first_user():
            token = self._settings.initial_invite_token
            if token is None:
                return  # unset - dev convenience, first registration is free
            if invite_code is None or not secrets.compare_digest(invite_code, token):
                raise InvalidInviteError("invalid initial invite token")
            return
        if invite_code is None:
            raise InvalidInviteError("an invite code is required to register")
        self._invite_service.consume_invite(invite_code, kind="invite")

    def register(
        self, email: str, username: str, full_name: str, password: str, invite_code: str | None = None
    ) -> UserModel:
        self._authorize_registration(invite_code)
        # Roll back explicitly rather than relying on the caller's session lifecycle to undo the
        # invite consumption above (a flush, not a commit - see InviteService.consume_invite) -
        # true for a normal request (api/deps.py::get_db_session rolls back on close anyway), but
        # this keeps the "a failed registration doesn't burn the invite" guarantee true regardless
        # of what the caller does with the session afterward.
        if self._session.scalar(select(UserModel).where(UserModel.email == email)) is not None:
            self._session.rollback()
            raise EmailAlreadyExistsError(f"email {email} is already registered")
        if self._session.scalar(select(UserModel).where(UserModel.username == username)) is not None:
            self._session.rollback()
            raise UsernameAlreadyExistsError(f"username {username} is already taken")

        user = UserModel(
            email=email,
            username=username,
            full_name=full_name,
            password_hash=_hasher.hash(password),
        )
        self._session.add(user)
        try:
            self._session.commit()
        except IntegrityError:
            # Lost the race against another registration between the checks above and this commit
            # (docs/TODO/CODE-REVIEW.md #8) - re-run the same checks to surface the right typed
            # error instead of letting the raw IntegrityError reach main.py unmapped (500). The
            # commit only fails on email or username, so one of these two is guaranteed to hit now.
            self._session.rollback()
            if self._session.scalar(select(UserModel).where(UserModel.email == email)) is not None:
                raise EmailAlreadyExistsError(f"email {email} is already registered") from None
            raise UsernameAlreadyExistsError(f"username {username} is already taken") from None
        return user

    def update_profile(
        self, user: UserModel, username: str | None = None, full_name: str | None = None
    ) -> UserModel:
        """Roadmap point E - profile edit page. Both args are None-means-"leave unchanged" (PATCH
        semantics), mirroring UpdateProfileIn."""
        if username is not None and username != user.username:
            existing = self._session.scalar(select(UserModel).where(UserModel.username == username))
            if existing is not None:
                raise UsernameAlreadyExistsError(f"username {username} is already taken")
            user.username = username
        if full_name is not None:
            user.full_name = full_name
        try:
            self._session.commit()
        except IntegrityError:
            # Same race as register(), but only username is writable here.
            self._session.rollback()
            raise UsernameAlreadyExistsError(f"username {username} is already taken") from None
        return user

    def set_skin(self, user: UserModel, person_id: UUID | None) -> UserModel:
        """Roadmap point E - cosmetic avatar. Person existence against Immich is validated by the
        route handler (api/auth_api.py), not here - AuthService has no ImmichService dependency by
        design, same separation as the rest of this module."""
        user.skin_person_id = person_id
        self._session.commit()
        return user

    def authenticate(self, email: str, password: str) -> UserModel:
        user = self._session.scalar(select(UserModel).where(UserModel.email == email))
        # Same error whether the email doesn't exist or the password is wrong - never reveal
        # which one it was.
        if user is None:
            raise InvalidCredentialsError("invalid email or password")
        try:
            _hasher.verify(user.password_hash, password)
        except VerifyMismatchError as exc:
            raise InvalidCredentialsError("invalid email or password") from exc
        return user

    def create_access_token(self, user: UserModel) -> str:
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=self._settings.jwt_expire_days)
        payload = {"sub": str(user.id), "iat": now, "exp": expires_at}
        return jwt.encode(payload, self._settings.jwt_secret, algorithm=_JWT_ALGORITHM)

    def get_user_from_token(self, token: str) -> UserModel:
        try:
            payload = jwt.decode(token, self._settings.jwt_secret, algorithms=[_JWT_ALGORITHM])
            user_id = UUID(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
            raise UnauthorizedError("invalid or expired session") from exc

        user = self._session.get(UserModel, user_id)
        if user is None:
            raise UnauthorizedError("invalid or expired session")

        # Session revocation (roadmap #H, F0): a token minted before the last password change is
        # stale even if it hasn't expired yet - reject it so "change password" really does log out
        # every other device. `iat` is read with .get, not [], because tokens issued before this
        # code shipped have no `iat` claim at all - treating that as "nothing to compare, don't
        # reject" avoids a mass forced-logout the moment this deploys; those old tokens just don't
        # get revocation coverage until they naturally expire. Strict `<` with `password_changed_at`
        # truncated to whole seconds: PATCH /auth/me/password re-issues the cookie in the same
        # request that sets password_changed_at, so an iat equal to it (truncated) must still pass.
        issued_at = payload.get("iat")
        if user.password_changed_at is not None and issued_at is not None:
            # timegm(...utctimetuple()), not .timestamp() - password_changed_at round-trips through
            # a plain (non-timezone) DB column, same convention as every other timestamp column in
            # this app (see persistence/users.py), so it can come back tz-naive. .timestamp() on a
            # naive datetime interprets it in the *local* system timezone, silently corrupting this
            # comparison by however many hours the host is offset from UTC. utctimetuple() treats a
            # naive value as already-UTC (a no-op) and correctly converts an aware one - exactly what
            # every value assigned to this column actually is (datetime.now(UTC), always) - and
            # matches how PyJWT itself encodes the iat/exp claims being compared against.
            changed_at = timegm(user.password_changed_at.utctimetuple())
            if issued_at < changed_at:
                raise UnauthorizedError("invalid or expired session")
        return user

    def change_password(self, user: UserModel, current_password: str, new_password: str) -> UserModel:
        try:
            _hasher.verify(user.password_hash, current_password)
        except VerifyMismatchError as exc:
            raise InvalidCredentialsError("current password is incorrect") from exc
        user.password_hash = _hasher.hash(new_password)
        user.password_changed_at = datetime.now(UTC)
        self._session.commit()
        return user
