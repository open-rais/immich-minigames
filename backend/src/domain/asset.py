"""Corresponds to Immich assets (photo or video)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID

AssetType = Literal["IMAGE", "VIDEO"]


@dataclass(frozen=True)
class Asset:
    id: UUID
    type: AssetType
    file_created_at: datetime
    # Calendar day the photo was taken in the device's local timezone (Immich's `localDateTime`),
    # not the UTC day of `file_created_at`. This is the day Dateguessr/Timeline compare against - a
    # photo taken at 23:30 local can fall on the next UTC day, which would otherwise mark a correct
    # local-day guess as off by one.
    local_date: date
    original_file_name: str
    width: int | None
    height: int | None
    is_favorite: bool
    latitude: float | None
    longitude: float | None
    city: str | None
    state: str | None
    country: str | None
