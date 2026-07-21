"""Auth REST endpoints - registration/login/logout/current-user for this app's own accounts
(roadmap point B). Mounted under /auth by api/api.py. Routes don't catch auth_service's domain
exceptions (EmailAlreadyExistsError etc.) - those propagate to the app-level handlers registered
in main.py, same pattern as api/api.py's own routes."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from api.auth_schemas import LoginIn, RegisterIn, UpdateProfileIn, UpdateSkinIn, UserOut
from api.deps import get_db_session, get_immich_service
from api.rate_limit import limiter
from config import get_settings
from persistence.users import UserModel
from services.auth_service import AuthService, UnauthorizedError
from services.immich_service import ImmichService

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


def get_current_user_optional(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> UserModel | None:
    """Same cookie read as get_current_user, but never raises - used where a route serves both
    anonymous and logged-in requests (see api/api.py's create_game/get_game_records) and just
    wants "the account if there is one", not to require auth. An invalid/expired token is treated
    the same as no cookie at all rather than surfacing as an error."""
    if access_token is None:
        return None
    try:
        return auth_service.get_user_from_token(access_token)
    except UnauthorizedError:
        return None


def _cookie_attrs() -> dict[str, object]:
    """Shared between _set_session_cookie and logout - browsers match a cookie for deletion by
    (name, domain, path), but several also expect SameSite/Secure/HttpOnly to match for the
    deletion to reliably take (docs/TODO/CODE-REVIEW.md #12) - reading both from here means they
    can't drift again. SameSite=Lax already blocks the cookie from riding along on cross-site
    POSTs, which covers CSRF for what this endpoint set does today. secure comes from
    settings.cookie_secure (docs/TODO/CODE-REVIEW.md #11) - false by default since the dev stack
    and docker-compose.app.yml both serve plain HTTP, set true behind a TLS-terminating proxy."""
    return {
        "path": "/",
        "httponly": True,
        "samesite": "lax",
        "secure": get_settings().cookie_secure,
    }


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=get_settings().jwt_expire_days * 24 * 60 * 60,
        **_cookie_attrs(),
    )


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit("3/minute")
def register(
    request: Request,
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
@limiter.limit("5/minute")
def login(
    request: Request,
    body: LoginIn,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOut:
    user = auth_service.authenticate(body.email, body.password)
    _set_session_cookie(response, auth_service.create_access_token(user))
    return UserOut.from_user(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(_COOKIE_NAME, **_cookie_attrs())


@router.get("/me", response_model=UserOut)
def get_me(user: Annotated[UserModel, Depends(get_current_user)]) -> UserOut:
    return UserOut.from_user(user)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UpdateProfileIn,
    user: Annotated[UserModel, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOut:
    updated = auth_service.update_profile(user, username=body.username, full_name=body.full_name)
    return UserOut.from_user(updated)


@router.put("/me/skin", response_model=UserOut)
def update_skin(
    body: UpdateSkinIn,
    user: Annotated[UserModel, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> UserOut:
    if body.person_id is not None:
        found = immich_service.get_persons(ids=frozenset({body.person_id}), limit=1)
        if not found:
            raise HTTPException(status_code=404, detail=f"person {body.person_id} not found")
    updated = auth_service.set_skin(user, body.person_id)
    return UserOut.from_user(updated)
