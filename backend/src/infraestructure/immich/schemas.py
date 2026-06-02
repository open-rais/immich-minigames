from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class PersonDTO:
    """Data Transfer Object for Immich Person."""
    id: str
    name: str
    asset_count: int
    thumbnail_url: str | None = None


@dataclass
class AlbumDTO:
    """Data Transfer Object for Immich Album."""
    id: str
    album_name: str
    asset_count: int


@dataclass
class AssetDTO:
    """Data Transfer Object for Immich Asset."""
    id: str
    file_created_at: datetime
    file_modified_at: datetime
    metadata: dict[str, Any]


@dataclass
class ImmichHealthDTO:
    """Data Transfer Object for Immich Health."""
    success: bool
    version: str
