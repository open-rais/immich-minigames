"""Player-facing metadata-reporting endpoint - lets any logged-in account flag a person/album/asset
as having bad metadata. Mounted under /reports by api/api.py."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from api.auth_api import get_current_user
from api.deps import get_reports_service
from api.dto.reports import CreateReportIn
from api.rate_limit import REPORT_LIMIT, limiter
from persistence.users import UserModel
from services.reports_service import ReportsService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=201, response_model=None)
@limiter.limit(REPORT_LIMIT)
def create_report(
    request: Request,
    body: CreateReportIn,
    user: Annotated[UserModel, Depends(get_current_user)],
    reports_service: Annotated[ReportsService, Depends(get_reports_service)],
) -> None:
    reports_service.create(
        user_id=user.id,
        entity_type=body.entity_type.value,
        entity_id=body.entity_id,
        reasons=[reason.value for reason in body.reasons],
        note=body.note,
    )
