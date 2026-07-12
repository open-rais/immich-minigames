"""Corresponds to Immich assets (photo or video)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

AssetType = Literal["IMAGE", "VIDEO"]


@dataclass(frozen=True)
class Asset:
    id: UUID
    type: AssetType
    file_created_at: datetime
    original_file_name: str
    width: int | None
    height: int | None
    is_favorite: bool
    latitude: float | None
    longitude: float | None
    city: str | None
    state: str | None
    country: str | None
