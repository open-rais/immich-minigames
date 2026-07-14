"""
Immich service: read-only queries against Immich's own Postgres database for game data, plus
thumbnail bytes via Immich's REST API for images - see docs/ARCHITECTURE/IMMICH.md's "Dos formas
de hablar con Immich" for why data queries and image serving use different paths.
"""

from datetime import date
from functools import lru_cache
from typing import Literal
from uuid import UUID

import httpx
from sqlalchemy import Date, cast, exists, func, select
from sqlalchemy.engine import Engine, Row

from config import Settings
from domain.asset import Asset
from domain.person import Person
from persistence.immich_tables import asset, asset_exif, asset_face, asset_file, get_engine, person

MediaType = Literal["photo", "video", "any"]


# Reused across requests (pooled connections, one client) instead of opening a new connection per
# thumbnail. A bounded timeout means a slow/hung Immich never blocks a worker thread indefinitely.
@lru_cache(maxsize=1)
def _get_http_client() -> httpx.Client:
    return httpx.Client(timeout=10.0)


class ImmichService:
    def __init__(self, engine: Engine | None = None, settings: Settings | None = None) -> None:
        self._engine = engine or get_engine()
        self._settings = settings or Settings()

    def get_assets(
        self,
        *,
        media_type: MediaType = "any",
        with_location: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        random: bool = False,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Asset]:
        has_thumbnail = exists(
            select(1).where(
                asset_file.c.assetId == asset.c.id,
                asset_file.c.type == "thumbnail",
            )
        )

        stmt = (
            select(
                asset.c.id,
                asset.c.type,
                asset.c.fileCreatedAt,
                # True local calendar day of the shot, timezone-of-session-independent: localDateTime
                # is a timestamptz whose UTC rendering is the local wall time, so casting to date at
                # UTC recovers the local day (see immich_tables.py / domain/asset.py).
                cast(func.timezone("UTC", asset.c.localDateTime), Date).label("localDate"),
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

        if exclude_ids:
            stmt = stmt.where(asset.c.id.notin_(exclude_ids))

        stmt = stmt.order_by(func.random() if random else asset.c.fileCreatedAt).limit(limit)

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()

        return [self._row_to_asset(row) for row in rows]

    def get_persons(
        self,
        *,
        named_only: bool = True,
        with_birthdate: bool | None = None,
        min_asset_count: int | None = None,
        name_query: str | None = None,
        ids: frozenset[UUID] | None = None,
        random: bool = False,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Person]:
        asset_count = func.count(func.distinct(asset_face.c.assetId)).label("asset_count")

        stmt = (
            select(person.c.id, person.c.name, person.c.birthDate, asset_count)
            .select_from(
                person.outerjoin(
                    asset_face,
                    (asset_face.c.personId == person.c.id)
                    & asset_face.c.deletedAt.is_(None)
                    & asset_face.c.isVisible.is_(True),
                )
            )
            .where(person.c.isHidden.is_(False), person.c.thumbnailPath != "")
            .group_by(person.c.id, person.c.name, person.c.birthDate)
        )

        if named_only:
            stmt = stmt.where(person.c.name != "")
        if with_birthdate is True:
            stmt = stmt.where(person.c.birthDate.is_not(None))
        elif with_birthdate is False:
            stmt = stmt.where(person.c.birthDate.is_(None))
        if name_query:
            stmt = stmt.where(person.c.name.ilike(f"%{name_query}%"))
        if ids is not None:
            stmt = stmt.where(person.c.id.in_(ids))
        if exclude_ids:
            stmt = stmt.where(person.c.id.notin_(exclude_ids))
        if min_asset_count is not None:
            stmt = stmt.having(asset_count >= min_asset_count)

        stmt = stmt.order_by(func.random() if random else person.c.name).limit(limit)

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()

        return [self._row_to_person(row) for row in rows]

    def get_person_first_asset_date(self, person_id: UUID) -> date | None:
        """Local calendar day of this person's earliest tagged asset - same local-day expression
        get_assets uses (see that method's localDate comment). Powers Immichdle's FirstAppearance
        clue. None if the person has no visible, non-deleted face tags."""
        local_date = cast(func.timezone("UTC", asset.c.localDateTime), Date)
        stmt = (
            select(func.min(local_date))
            .select_from(asset_face.join(asset, asset.c.id == asset_face.c.assetId))
            .where(
                asset_face.c.personId == person_id,
                asset_face.c.deletedAt.is_(None),
                asset_face.c.isVisible.is_(True),
                asset.c.status == "active",
                asset.c.visibility == "timeline",
                asset.c.deletedAt.is_(None),
            )
        )
        with self._engine.connect() as conn:
            return conn.execute(stmt).scalar()

    def get_assets_together_count(self, person_a_id: UUID, person_b_id: UUID) -> int:
        """How many distinct assets have both people face-tagged - powers Immichdle's
        AssetsTogether clue."""
        face_a = asset_face.alias("face_a")
        face_b = asset_face.alias("face_b")
        stmt = (
            select(func.count(func.distinct(face_a.c.assetId)))
            .select_from(face_a.join(face_b, face_a.c.assetId == face_b.c.assetId))
            .where(
                face_a.c.personId == person_a_id,
                face_a.c.deletedAt.is_(None),
                face_a.c.isVisible.is_(True),
                face_b.c.personId == person_b_id,
                face_b.c.deletedAt.is_(None),
                face_b.c.isVisible.is_(True),
            )
        )
        with self._engine.connect() as conn:
            return conn.execute(stmt).scalar() or 0

    def get_asset_thumbnail(self, asset_id: UUID, size: str = "preview") -> tuple[bytes, str]:
        """Fetches an asset's image bytes via Immich's REST API (not the DB - see module
        docstring). `size="preview"` (~1440px JPEG derivative) rather than the default `thumbnail`
        (~250px, too small for fullscreen) or `original` (may be HEIC/RAW/video, not safely
        renderable in a browser <img>).

        Raises httpx.HTTPStatusError (e.g. 404 - no thumbnail, 401 - bad IMMICH_API_KEY) or
        httpx.RequestError (Immich unreachable/timed out) - see api/api.py for how each maps to a
        response."""
        response = _get_http_client().get(
            f"{self._settings.immich_server_url}/api/assets/{asset_id}/thumbnail",
            params={"size": size},
            headers={"x-api-key": self._settings.immich_api_key},
        )
        response.raise_for_status()
        return response.content, response.headers.get("content-type", "image/jpeg")

    def get_person_thumbnail(self, person_id: UUID) -> tuple[bytes, str]:
        """Fetches a person's face thumbnail via Immich's REST API (not the DB - see module
        docstring). Returns (image bytes, content-type).

        Raises httpx.HTTPStatusError (e.g. 404 - no thumbnail, 401 - bad IMMICH_API_KEY) or
        httpx.RequestError (Immich unreachable/timed out) - see api/api.py for how each maps to a
        response."""
        response = _get_http_client().get(
            f"{self._settings.immich_server_url}/api/people/{person_id}/thumbnail",
            headers={"x-api-key": self._settings.immich_api_key},
        )
        response.raise_for_status()
        return response.content, response.headers.get("content-type", "image/jpeg")

    @staticmethod
    def _row_to_asset(row: Row) -> Asset:
        return Asset(
            id=row.id,
            type=row.type,
            file_created_at=row.fileCreatedAt,
            local_date=row.localDate,
            original_file_name=row.originalFileName,
            width=row.width,
            height=row.height,
            is_favorite=row.isFavorite,
            latitude=row.latitude,
            longitude=row.longitude,
            city=row.city,
            state=row.state,
            country=row.country,
        )

    @staticmethod
    def _row_to_person(row: Row) -> Person:
        return Person(
            id=row.id,
            name=row.name,
            birth_date=row.birthDate,
            asset_count=row.asset_count,
        )
