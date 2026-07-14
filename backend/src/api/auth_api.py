"""Auth REST endpoints - registration/login/logout/current-user for this app's own accounts
(roadmap point B). Mounted under /auth by api/api.py. Routes don't catch auth_service's domain
exceptions (EmailAlreadyExistsError etc.) - those propagate to the app-level handlers registered
in main.py, same pattern as api/api.py's own routes."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from api.auth_schemas import LoginIn, RegisterIn, UserOut
from api.deps import get_db_session
from config import Settings
from persistence.users import UserModel
from services.auth_service import AuthService, UnauthorizedError

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_NAME = "access_token"


def get_auth_service(session: Annotated[Session, Depends(get_db_session)]) -> AuthService:
    return AuthService(session)


def get_current_user(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> UserModel:
    if access_token is None:
        raise UnauthorizedError("not authenticated")
    return auth_service.get_user_from_token(access_token)


def _set_session_cookie(response: Response, token: str) -> None:
    # Secure=False for now - both the dev stack and the packaged docker-compose.app.yml serve
    # over plain HTTP (see frontend/nginx.conf.template); revisit if an HTTPS deployment is ever
    # documented. SameSite=Lax already blocks the cookie from riding along on cross-site POSTs,
    # which covers CSRF for what this endpoint set does today.
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=Settings().jwt_expire_days * 24 * 60 * 60,
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    body: RegisterIn,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOut:
    user = auth_service.register(
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        password=body.password,
    )
    _set_session_cookie(response, auth_service.create_access_token(user))
    return UserOut.from_user(user)


@router.post("/login", response_model=UserOut)
def login(
    body: LoginIn,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOut:
    user = auth_service.authenticate(body.email, body.password)
    _set_session_cookie(response, auth_service.create_access_token(user))
    return UserOut.from_user(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(_COOKIE_NAME)


@router.get("/me", response_model=UserOut)
def get_me(user: Annotated[UserModel, Depends(get_current_user)]) -> UserOut:
    return UserOut.from_user(user)
