"""
Immich service: read-only queries against Immich's own Postgres database (not its REST API - see
docs/ARCHITECTURE/IMMICH.md for why). Games use this to fetch candidate assets/people.
"""

from datetime import date
from typing import Literal
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.engine import Engine, Row

from domain.asset import Asset
from domain.person import Person
from persistance.immich_tables import asset, asset_exif, asset_face, asset_file, get_engine, person

MediaType = Literal["photo", "video", "any"]


class ImmichService:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

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
        if exclude_ids:
            stmt = stmt.where(person.c.id.notin_(exclude_ids))
        if min_asset_count is not None:
            stmt = stmt.having(asset_count >= min_asset_count)

        stmt = stmt.order_by(func.random() if random else person.c.name).limit(limit)

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()

        return [self._row_to_person(row) for row in rows]

    @staticmethod
    def _row_to_asset(row: Row) -> Asset:
        return Asset(
            id=row.id,
            type=row.type,
            file_created_at=row.fileCreatedAt,
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
