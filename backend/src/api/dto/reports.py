"""Metadata-reporting DTOs - see services/reports_service.py."""

from uuid import UUID

from pydantic import BaseModel, Field

from games.report_spec import ReportEntity, ReportReason


class CreateReportIn(BaseModel):
    entity_type: ReportEntity
    entity_id: UUID
    reasons: list[ReportReason] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=200)
