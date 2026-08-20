"""Metadata-reporting DTOs - see services/reports_service.py."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from games.report_spec import ReportEntity, ReportReason


class CreateReportIn(BaseModel):
    entity_type: ReportEntity
    entity_id: UUID
    reasons: list[ReportReason] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=200)


class AdminReportOut(BaseModel):
    id: UUID
    entity_type: ReportEntity
    entity_id: UUID
    # None when the entity no longer exists in Immich (deleted since the report was filed).
    entity_name: str | None
    reason: ReportReason
    note: str | None
    user_id: UUID
    username: str
    solved: bool
    solved_at: datetime | None
    created_at: datetime


class AdminReportCountsOut(BaseModel):
    asset: int
    person: int
    album: int


class UpdateReportIn(BaseModel):
    solved: bool
