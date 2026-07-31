"""Postgres queries over Immich's `asset`/`asset_exif` tables."""

import math
from datetime import date
from typing import Literal
from uuid import UUID

from sqlalchemy import Date, cast, exists, extract, func, select
from sqlalchemy.engine import Engine

from domain.asset import Asset
from persistence.immich_tables import asset, asset_exif, asset_file

from ._random import sample_by_id_pivot
from ._rows import row_to_asset

MediaType = Literal["photo", "video", "any"]


def get_assets(
    engine: Engine,
    *,
    media_type: MediaType = "any",
    with_location: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    local_date: date | None = None,
    local_month: int | None = None,
    near_km: tuple[float, float, float] | None = None,
    randomize: bool = False,
    limit: int = 1,
    exclude_ids: frozenset[UUID] = frozenset(),
) -> list[Asset]:
    has_thumbnail = exists(
        select(1).where(
            asset_file.c.assetId == asset.c.id,
            asset_file.c.type == "thumbnail",
        )
    )

    # True local calendar day of the shot, timezone-of-session-independent: localDateTime
    # is a timestamptz whose UTC rendering is the local wall time, so casting to date at
    # UTC recovers the local day (see immich_tables.py / domain/asset.py).
    local_date_expr = cast(func.timezone("UTC", asset.c.localDateTime), Date)

    stmt = (
        select(
            asset.c.id,
            asset.c.type,
            asset.c.fileCreatedAt,
            local_date_expr.label("localDate"),
            asset.c.originalFileName,
            asset.c.width,
            asset.c.height,
            asset.c.isFavorite,
            asset_exif.c.latitude,
            asset_exif.c.longitude,
            asset_exif.c.city,
            asset_exif.c.state,
            asset_exif.c.country,
        )
        .select_from(asset.outerjoin(asset_exif, asset_exif.c.assetId == asset.c.id))
        .where(
            asset.c.status == "active",
            asset.c.visibility == "timeline",
            asset.c.deletedAt.is_(None),
            has_thumbnail,
        )
    )

    if media_type == "photo":
        stmt = stmt.where(asset.c.type == "IMAGE")
    elif media_type == "video":
        stmt = stmt.where(asset.c.type == "VIDEO")

    if with_location is True:
        stmt = stmt.where(asset_exif.c.latitude.is_not(None), asset_exif.c.longitude.is_not(None))
    elif with_location is False:
        stmt = stmt.where(asset_exif.c.latitude.is_(None), asset_exif.c.longitude.is_(None))

    if date_from is not None:
        stmt = stmt.where(asset.c.fileCreatedAt >= date_from)
    if date_to is not None:
        stmt = stmt.where(asset.c.fileCreatedAt <= date_to)

    if local_date is not None:
        stmt = stmt.where(local_date_expr == local_date)
    if local_month is not None:
        stmt = stmt.where(extract("month", local_date_expr) == local_month)

    if near_km is not None:
        # Coarse lat/lon bounding-box prefilter (box, not circle) - callers that need the exact
        # circle (e.g. games/geoguessr.py's 500m rule) do a precise haversine post-filter
        # themselves. Degrees-per-km approximation: 111.0 km/degree of latitude everywhere,
        # scaled by cos(latitude) for longitude.
        lat, lon, radius_km = near_km
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 1e-6))
        stmt = stmt.where(
            asset_exif.c.latitude.between(lat - lat_delta, lat + lat_delta),
            asset_exif.c.longitude.between(lon - lon_delta, lon + lon_delta),
        )

    if exclude_ids:
        stmt = stmt.where(asset.c.id.notin_(exclude_ids))

    with engine.connect() as conn:
        if randomize:
            # Pivot on asset.id (see ._random's docstring for why that's safe) instead of
            # `ORDER BY random()`, which would force a full scan+sort of every matching asset.
            rows = sample_by_id_pivot(conn, stmt, asset.c.id, limit)
        else:
            rows = conn.execute(stmt.order_by(asset.c.fileCreatedAt).limit(limit)).all()

    return [row_to_asset(row) for row in rows]
