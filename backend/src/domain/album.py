"""Corresponds to Immich albums."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Album:
    id: UUID
    name: str
    asset_count: int
    # Immich's chosen cover asset (album.albumThumbnailAssetId), or None if the album has none set -
    # ImmichService.get_album_cover_asset_id falls back to the album's first asset in that case.
    thumbnail_asset_id: UUID | None
