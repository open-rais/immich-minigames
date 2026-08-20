"""Player-facing metadata-reporting endpoints - lets any logged-in account flag a person/album/asset
as having bad metadata, and see what it's about to report before doing so. Mounted under /reports
by api/api.py."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from api.auth_api import get_current_user
from api.deps import get_immich_service, get_reports_service
from api.dto.reports import CreateReportIn, ReportContextOut
from api.rate_limit import REPORT_LIMIT, SEARCH_LIMIT, limiter
from games.report_spec import ReportEntity
from persistence.users import UserModel
from services.immich import ImmichService
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


@router.get("/context", response_model=ReportContextOut | None)
@limiter.limit(SEARCH_LIMIT)
def get_report_context(
    request: Request,
    entity_type: ReportEntity,
    entity_id: UUID,
    _user: Annotated[UserModel, Depends(get_current_user)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
) -> ReportContextOut | None:
    """What the report modal shows the player above the reason checkboxes - not validated against
    open reports or anything else, just a straight lookup by id. None (not 404) when the entity no
    longer exists in Immich - same non-blocking stance as the rest of this feature (reporting
    itself never depends on the entity still existing), so the modal just renders without a context
    panel instead of erroring."""
    if entity_type == ReportEntity.PERSON:
        persons = immich_service.get_persons(ids=frozenset({entity_id}), named_only=False, limit=1)
        if not persons:
            return None
        return ReportContextOut(name=persons[0].name, birth_date=persons[0].birth_date)

    if entity_type == ReportEntity.ALBUM:
        albums = immich_service.get_albums(ids=frozenset({entity_id}), limit=1)
        if not albums:
            return None
        return ReportContextOut(
            name=albums[0].name,
            start_date=immich_service.get_album_first_asset_date(entity_id),
            end_date=immich_service.get_album_last_asset_date(entity_id),
        )

    assets = immich_service.get_assets(ids=frozenset({entity_id}), limit=1)
    if not assets:
        return None
    asset = assets[0]
    return ReportContextOut(
        latitude=asset.latitude,
        longitude=asset.longitude,
        city=asset.city,
        country=asset.country,
        start_date=asset.local_date,
        persons=immich_service.get_named_persons_in_asset(entity_id),
    )
