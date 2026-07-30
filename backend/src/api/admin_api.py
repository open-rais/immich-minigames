"""Admin REST endpoints (ADMIN-FEATURE.md point #3) - lets an is_admin account list and edit any
user's full name/username/skin. Mounted under /admin by api/api.py. Reuses auth_api.py's
get_current_user dependency and auth_schemas.py's DTOs (UpdateProfileIn/UpdateSkinIn/UserOut) -
these are the same shapes the self-service /auth/me routes already accept/return, just applied to
an arbitrary user_id instead of the caller's own account."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth_api import get_auth_service, get_current_user
from api.auth_schemas import UpdateProfileIn, UpdateSkinIn, UserOut
from api.deps import get_immich_service, get_invite_service
from api.dto.admin import CreateInviteOut
from audit import audit
from persistence.users import UserModel
from services.auth_service import AuthService
from services.immich_service import ImmichService
from services.invite_service import InviteService

router = APIRouter(prefix="/admin", tags=["admin"])


def get_current_admin_user(user: Annotated[UserModel, Depends(get_current_user)]) -> UserModel:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin access required")
    return user


def _get_target_user(auth_service: AuthService, user_id: UUID) -> UserModel:
    user = auth_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"user {user_id} not found")
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> list[UserOut]:
    return [UserOut.from_user(u) for u in auth_service.list_users(offset=offset, limit=limit)]


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    body: UpdateProfileIn,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOut:
    target = _get_target_user(auth_service, user_id)
    updated = auth_service.update_profile(target, username=body.username, full_name=body.full_name)
    return UserOut.from_user(updated)


@router.post("/users/{user_id}/password-reset", response_model=CreateInviteOut, status_code=201)
def create_password_reset(
    user_id: UUID,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    invite_service: Annotated[InviteService, Depends(get_invite_service)],
) -> CreateInviteOut:
    target = _get_target_user(auth_service, user_id)
    invite, token = invite_service.create_invite(kind="password_reset", user_id=target.id)
    # In addition to invite_service's own generic invite_created (LOGGING.md §4.4) - this one
    # carries target_user_id, which invite_service has no reason to know about.
    audit(
        "password_reset_created",
        target_user_id=str(target.id),
        invite_id=str(invite.id),
        expires_at=invite.expires_at.isoformat(),
    )
    return CreateInviteOut(id=invite.id, token=token, expires_at=invite.expires_at)


@router.put("/users/{user_id}/skin", response_model=UserOut)
def update_user_skin(
    user_id: UUID,
    body: UpdateSkinIn,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> UserOut:
    target = _get_target_user(auth_service, user_id)
    if body.person_id is not None:
        found = immich_service.get_persons(ids=frozenset({body.person_id}), limit=1)
        if not found:
            raise HTTPException(status_code=404, detail=f"person {body.person_id} not found")
    updated = auth_service.set_skin(target, body.person_id)
    return UserOut.from_user(updated)
