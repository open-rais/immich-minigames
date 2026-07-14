"""
Auth service - registers/authenticates this app's own user accounts (roadmap point B) and
issues/verifies their login JWT. Entirely separate from Immich's own users (never touches
Immich's Postgres schema) and, for now, separate from the anonymous X-Owner-Id scheme that games
still use (see games_service.py/ownerId.ts) - accounts and anonymous play coexist; connecting
Game.owner to a real account is a later roadmap point (F).

Session model: stateless JWT in an httpOnly cookie, no server-side session table - "logout" just
clears the cookie client-side, a token copied before logout stays valid until it expires
(JWT_EXPIRE_DAYS). Accepted tradeoff for "lo básico" (see docs/TODO/ROADMAP.md point B) - revisit
if real revocation is ever needed.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import Settings
from persistence.users import UserModel

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
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or Settings()

    def register(self, email: str, username: str, full_name: str, password: str) -> UserModel:
        if self._session.scalar(select(UserModel).where(UserModel.email == email)) is not None:
            raise EmailAlreadyExistsError(f"email {email} is already registered")
        if self._session.scalar(select(UserModel).where(UserModel.username == username)) is not None:
            raise UsernameAlreadyExistsError(f"username {username} is already taken")

        user = UserModel(
            email=email,
            username=username,
            full_name=full_name,
            password_hash=_hasher.hash(password),
        )
        self._session.add(user)
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
        expires_at = datetime.now(UTC) + timedelta(days=self._settings.jwt_expire_days)
        payload = {"sub": str(user.id), "exp": expires_at}
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
        return user
