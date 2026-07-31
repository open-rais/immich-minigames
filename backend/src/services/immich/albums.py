"""Postgres queries over Immich's `album`/`album_asset` tables."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from domain.album import Album
from persistence.immich_tables import album, album_asset

from ._rows import row_to_album


def get_albums(
    engine: Engine,
    *,
    randomize: bool = False,
    limit: int = 1,
    exclude_ids: frozenset[UUID] = frozenset(),
) -> list[Album]:
    """Non-deleted albums with their asset count - the data source for MoreOrLess's albumAssets
    mode (see games/more_or_less/album_assets.py), mirroring get_persons' shape
    (randomize/limit/exclude_ids). asset_count comes from the album_asset join; an album with no
    assets still comes back (count 0)."""
    asset_count = func.count(album_asset.c.assetId).label("asset_count")

    stmt = (
        select(album.c.id, album.c.albumName, album.c.albumThumbnailAssetId, asset_count)
        .select_from(album.outerjoin(album_asset, album_asset.c.albumId == album.c.id))
        .where(album.c.deletedAt.is_(None))
        .group_by(album.c.id, album.c.albumName, album.c.albumThumbnailAssetId)
    )

    if exclude_ids:
        stmt = stmt.where(album.c.id.notin_(exclude_ids))

    stmt = stmt.order_by(func.random() if randomize else album.c.albumName).limit(limit)

    with engine.connect() as conn:
        rows = conn.execute(stmt).all()

    return [row_to_album(row) for row in rows]


def get_album_cover_asset_id(engine: Engine, album_id: UUID) -> UUID | None:
    """The asset whose thumbnail represents this album: Immich's chosen cover
    (album.albumThumbnailAssetId) if set, else this album's first asset. None if the album
    doesn't exist or has no assets at all - the caller (api/api.py's album thumbnail route)
    maps that to a 404. The actual image bytes are then served via images.get_asset_thumbnail."""
    with engine.connect() as conn:
        cover_id = conn.execute(select(album.c.albumThumbnailAssetId).where(album.c.id == album_id)).scalar()
        if cover_id is not None:
            return cover_id
        return conn.execute(select(album_asset.c.assetId).where(album_asset.c.albumId == album_id).limit(1)).scalar()
