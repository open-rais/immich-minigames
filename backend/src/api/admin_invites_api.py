"""Admin REST endpoints for registration invites - lets an is_admin account generate/list/revoke
single-use, expiring invite links. Mounted under /admin/invites by
api/api.py. Mirrors api/admin_daily_api.py's shape closely - same get_current_admin_user
dependency, same router-per-subresource split."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from api.admin_api import get_current_admin_user
from api.deps import get_invite_service
from api.dto.admin import CreateInviteOut, InviteOut
from persistence.users import UserModel
from services.invite_service import InviteService

router = APIRouter(prefix="/admin/invites", tags=["admin"])

_KIND = "invite"


@router.post("", response_model=CreateInviteOut, status_code=201)
def create_invite(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    invite_service: Annotated[InviteService, Depends(get_invite_service)],
) -> CreateInviteOut:
    invite, token = invite_service.create_invite(kind=_KIND)
    return CreateInviteOut(id=invite.id, token=token, expires_at=invite.expires_at)


@router.get("", response_model=list[InviteOut])
def list_invites(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    invite_service: Annotated[InviteService, Depends(get_invite_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> list[InviteOut]:
    return [InviteOut.from_model(i) for i in invite_service.list_invites(kind=_KIND, offset=offset, limit=limit)]


@router.delete("/{invite_id}", status_code=204)
def revoke_invite(
    invite_id: UUID,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    invite_service: Annotated[InviteService, Depends(get_invite_service)],
) -> None:
    invite_service.revoke_invite(invite_id)
