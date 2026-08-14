"""
Auth service - registers/authenticates this app's own user accounts and issues/verifies their
login JWT. Entirely separate from Immich's own users (never touches Immich's Postgres schema).
Every game is tied to the account that created it via GameModel.user_id (see games_service.py) -
login is mandatory.

Session model: stateless JWT in an httpOnly cookie, no server-side session table - "logout" just
clears the cookie client-side, a token copied before logout stays valid until it expires
(JWT_EXPIRE_DAYS). Accepted tradeoff - revisit if real revocation is
ever needed.
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

from audit import audit
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
        """Newest-registered first, paginated (infinite-scroll UI, see api/admin_api.py) -
        offset/limit, same convention as ImmichService.search_persons."""
        stmt = select(UserModel).order_by(UserModel.created_at.desc()).offset(offset).limit(limit)
        return list(self._session.scalars(stmt))

    def get_user_by_id(self, user_id: UUID) -> UserModel | None:
        """Looks up any account by id, not just the caller's own (unlike get_user_from_token,
        which is JWT-subject-bound)."""
        return self._session.get(UserModel, user_id)

    def _is_first_user(self) -> bool:
        return self._session.scalar(select(UserModel.id).limit(1)) is None

    def _authorize_registration(self, email: str, invite_code: str | None) -> str:
        """Registration is invite-only, except for the very first account (which can't have an
        invite yet). Raises InvalidInviteError, never returns a reason to the caller - same
        anti-enumeration shape as InviteService.consume_invite (the real reason still goes to the
        audit log via register_rejected - only the HTTP response stays generic). Returns `via`
        ("first_user"/"bootstrap_token"/"invite") for register()'s register_ok event on the
        success path."""
        if self._is_first_user():
            token = self._settings.initial_invite_token
            if not token:
                # Falsy, not `is None` - an unset INITIAL_INVITE_TOKEN reaches here as ""
                # (empty string), not None, whenever it's set via a blank
                # `INITIAL_INVITE_TOKEN=` line (.env.example's own documented default) or Docker
                # Compose's `${INITIAL_INVITE_TOKEN}` interpolation with no var defined (Compose
                # always injects the key with an empty-string value in that case, never omits it -
                # verified with `docker compose config`). An `is None` check here would silently
                # lock every fresh install's first registration behind an invite code that can
                # never be satisfied (nothing ever submits an empty string as one).
                return "first_user"  # unset (or blank) - dev convenience, first registration is free
            if invite_code is None or not secrets.compare_digest(invite_code, token):
                audit("register_rejected", email=email, reason="invalid initial invite token")
                raise InvalidInviteError("invalid initial invite token")
            return "bootstrap_token"
        if invite_code is None:
            audit("register_rejected", email=email, reason="an invite code is required to register")
            raise InvalidInviteError("an invite code is required to register")
        try:
            self._invite_service.consume_invite(invite_code, kind="invite")
        except InvalidInviteError as exc:
            audit("register_rejected", email=email, reason=str(exc))
            raise
        return "invite"

    def register(
        self, email: str, username: str, full_name: str, password: str, invite_code: str | None = None
    ) -> UserModel:
        via = self._authorize_registration(email, invite_code)
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
            # - re-run the same checks to surface the right typed error instead of letting the
            # raw IntegrityError reach main.py unmapped (500). The
            # commit only fails on email or username, so one of these two is guaranteed to hit now.
            self._session.rollback()
            if self._session.scalar(select(UserModel).where(UserModel.email == email)) is not None:
                raise EmailAlreadyExistsError(f"email {email} is already registered") from None
            raise UsernameAlreadyExistsError(f"username {username} is already taken") from None
        audit("register_ok", user_id=str(user.id), email=email, via=via)
        return user

    def update_profile(self, user: UserModel, username: str | None = None, full_name: str | None = None) -> UserModel:
        """Profile edit page. Both args are None-means-"leave unchanged" (PATCH semantics),
        mirroring UpdateProfileIn."""
        changed = []
        if username is not None and username != user.username:
            existing = self._session.scalar(select(UserModel).where(UserModel.username == username))
            if existing is not None:
                raise UsernameAlreadyExistsError(f"username {username} is already taken")
            user.username = username
            changed.append("username")
        if full_name is not None:
            user.full_name = full_name
            changed.append("full_name")
        try:
            self._session.commit()
        except IntegrityError:
            # Same race as register(), but only username is writable here.
            self._session.rollback()
            raise UsernameAlreadyExistsError(f"username {username} is already taken") from None
        # The actor (self-service caller or an admin editing someone else) is implicit in the
        # request context - one event covers both cases, since AuthService has no
        # way to tell them apart itself (both routes call this same method).
        if changed:
            audit("profile_updated", target_user_id=str(user.id), fields=changed)
        return user

    def set_skin(self, user: UserModel, person_id: UUID | None) -> UserModel:
        """Cosmetic avatar. Person existence against Immich is validated by the route handler
        (api/auth_api.py), not here - AuthService has no ImmichService dependency by design, same
        separation as the rest of this module."""
        user.skin_person_id = person_id
        self._session.commit()
        audit("skin_updated", target_user_id=str(user.id), fields=["skin_person_id"])
        return user

    def authenticate(self, email: str, password: str) -> UserModel:
        user = self._session.scalar(select(UserModel).where(UserModel.email == email))
        # Same error whether the email doesn't exist or the password is wrong - never reveal
        # which one it was.
        if user is None:
            audit("login_failed", email=email)
            raise InvalidCredentialsError("invalid email or password")
        try:
            _hasher.verify(user.password_hash, password)
        except VerifyMismatchError as exc:
            audit("login_failed", email=email, user_id=str(user.id))
            raise InvalidCredentialsError("invalid email or password") from exc
        audit("login_ok", email=email, user_id=str(user.id))
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

        # Session revocation: a token minted before the last password change is stale even if it
        # hasn't expired yet - reject it so "change password" really does log out every other
        # device. `iat` is read with .get, not [], because tokens issued before this revocation
        # check existed have no `iat` claim at all - treating that as "nothing to compare, don't
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
            audit("password_change_failed", user_id=str(user.id))
            raise InvalidCredentialsError("current password is incorrect") from exc
        user.password_hash = _hasher.hash(new_password)
        user.password_changed_at = datetime.now(UTC)
        self._session.commit()
        audit("password_change_ok", user_id=str(user.id))
        return user

    def reset_password(self, token: str, new_password: str) -> UserModel:
        """The public counterpart of change_password: proof of identity is the admin-issued token
        (services/invite_service.py, kind="password_reset") instead of the current password, for a
        caller who's locked out and by definition has no session to re-issue a cookie for (unlike
        change_password, this never touches the response cookie - the frontend sends them to
        /login afterward)."""
        try:
            invite = self._invite_service.consume_invite(token, kind="password_reset")
        except InvalidInviteError as exc:
            audit("password_reset_failed", reason=str(exc))
            raise
        user = self._session.get(UserModel, invite.user_id)
        user.password_hash = _hasher.hash(new_password)
        user.password_changed_at = datetime.now(UTC)
        self._session.commit()
        audit("password_reset_ok", user_id=str(user.id))
        return user
