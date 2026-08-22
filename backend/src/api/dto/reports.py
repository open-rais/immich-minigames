"""Metadata-reporting DTOs - see services/reports_service.py."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from games.report_spec import ReportEntity, ReportReason


class CreateReportIn(BaseModel):
    entity_type: ReportEntity
    entity_id: UUID
    reasons: list[ReportReason] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=200)


class ReportContextOut(BaseModel):
    """What the report modal shows above the reason checkboxes, so the player can see exactly
    which person/asset/album they're about to report - sparse by design (only the fields that
    apply to the given entity_type are set), one shape rather than a Union of three, since a
    caller always already knows entity_type from the request it made."""

    name: str | None = None  # person or album
    birth_date: date | None = None  # person
    latitude: float | None = None  # asset
    longitude: float | None = None  # asset
    city: str | None = None  # asset
    country: str | None = None  # asset
    start_date: date | None = None  # asset's own date, or an album's earliest asset's date
    end_date: date | None = None  # album's most recent asset's date
    persons: list[str] | None = None  # asset - names of people tagged in it


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
