"""Admin REST endpoints for the metadata-reporting feature - three paginated lists (one per
entity type), an open-report count per type, and marking a report resolved/unresolved. Mounted
under /admin/reports by api/api.py. Mirrors api/admin_invites_api.py's shape closely - same
get_current_admin_user dependency, same router-per-subresource split."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from api.admin_api import get_current_admin_user
from api.auth_api import get_auth_service
from api.deps import get_immich_service, get_reports_service
from api.dto.reports import AdminReportCountsOut, AdminReportOut, UpdateReportIn
from games.report_spec import ReportEntity
from persistence.reports import ReportModel
from persistence.users import UserModel
from services.auth_service import AuthService
from services.immich import ImmichService
from services.reports_service import ReportsService

router = APIRouter(prefix="/admin/reports", tags=["admin"])


def _resolve_entity_names(
    immich_service: ImmichService, entity_type: ReportEntity, entity_ids: set[UUID]
) -> dict[UUID, str]:
    if not entity_ids:
        return {}
    ids = frozenset(entity_ids)
    if entity_type == ReportEntity.PERSON:
        return {p.id: p.name for p in immich_service.get_persons(ids=ids, named_only=False, limit=len(ids))}
    if entity_type == ReportEntity.ALBUM:
        return {a.id: a.name for a in immich_service.get_albums(ids=ids, limit=len(ids))}
    return {a.id: a.original_file_name for a in immich_service.get_assets(ids=ids, limit=len(ids))}


def _to_admin_out(
    reports: list[ReportModel], entity_names: dict[UUID, str], usernames: dict[UUID, str]
) -> list[AdminReportOut]:
    return [
        AdminReportOut(
            id=r.id,
            entity_type=ReportEntity(r.entity_type),
            entity_id=r.entity_id,
            entity_name=entity_names.get(r.entity_id),
            reason=r.reason,
            note=r.note,
            user_id=r.user_id,
            username=usernames.get(r.user_id, ""),
            solved=r.solved,
            solved_at=r.solved_at,
            created_at=r.created_at,
        )
        for r in reports
    ]


@router.get("", response_model=list[AdminReportOut])
def list_reports(
    entity_type: ReportEntity,
    solved: bool,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    reports_service: Annotated[ReportsService, Depends(get_reports_service)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[AdminReportOut]:
    reports = reports_service.list(entity_type.value, solved, offset=offset, limit=limit)
    entity_names = _resolve_entity_names(immich_service, entity_type, {r.entity_id for r in reports})
    usernames = auth_service.usernames_for({r.user_id for r in reports})
    return _to_admin_out(reports, entity_names, usernames)


@router.get("/counts", response_model=AdminReportCountsOut)
def get_report_counts(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    reports_service: Annotated[ReportsService, Depends(get_reports_service)],
) -> AdminReportCountsOut:
    counts = reports_service.counts()
    return AdminReportCountsOut(
        asset=counts.get("asset", 0), person=counts.get("person", 0), album=counts.get("album", 0)
    )


@router.patch("/{report_id}", response_model=AdminReportOut)
def update_report(
    report_id: UUID,
    body: UpdateReportIn,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    reports_service: Annotated[ReportsService, Depends(get_reports_service)],
    immich_service: Annotated[ImmichService, Depends(get_immich_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AdminReportOut:
    report = reports_service.set_solved(report_id, body.solved)
    entity_type = ReportEntity(report.entity_type)
    entity_names = _resolve_entity_names(immich_service, entity_type, {report.entity_id})
    usernames = auth_service.usernames_for({report.user_id})
    return _to_admin_out([report], entity_names, usernames)[0]
