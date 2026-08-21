"""
Immich service: read-only queries against Immich's own Postgres database for game data, plus
thumbnail bytes via Immich's REST API for images - see docs/ARCHITECTURE/IMMICH.md's "Dos formas
de hablar con Immich" for why data queries and image serving use different paths.

Split by transport (8 methods hit Postgres, 2 hit Immich's REST API over httpx) and, within
Postgres, by entity - assets.py/persons.py/albums.py/faces.py. ImmichService itself stays a thin
facade over those modules: ~50 call sites across every game, every daily.py, the registry,
deps.py and the tests receive an ImmichService, so the facade keeps that surface exactly as it
was rather than forcing each call site to depend on multiple injected services.
"""

from datetime import date
from typing import Protocol
from uuid import UUID

from sqlalchemy.engine import Engine

from config import Settings, get_settings
from domain.album import Album
from domain.asset import Asset
from domain.face import Face
from domain.person import Person
from persistence.immich_db import get_immich_engine

from . import albums, assets, faces, images, persons
from .assets import MediaType

__all__ = ["ContentQueries", "ImmichService", "MediaType"]


class ImmichService:
    def __init__(self, engine: Engine | None = None, settings: Settings | None = None) -> None:
        self._engine = engine or get_immich_engine()
        self._settings = settings or get_settings()

    def get_assets(
        self,
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
        ids: frozenset[UUID] | None = None,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Asset]:
        return assets.get_assets(
            self._engine,
            media_type=media_type,
            with_location=with_location,
            date_from=date_from,
            date_to=date_to,
            local_date=local_date,
            local_month=local_month,
            near_km=near_km,
            randomize=randomize,
            limit=limit,
            ids=ids,
            exclude_ids=exclude_ids,
        )

    def get_persons(
        self,
        *,
        named_only: bool = True,
        with_birthdate: bool | None = None,
        min_asset_count: int | None = None,
        name_query: str | None = None,
        ids: frozenset[UUID] | None = None,
        randomize: bool = False,
        asset_count_weight: float | None = None,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Person]:
        return persons.get_persons(
            self._engine,
            named_only=named_only,
            with_birthdate=with_birthdate,
            min_asset_count=min_asset_count,
            name_query=name_query,
            ids=ids,
            randomize=randomize,
            asset_count_weight=asset_count_weight,
            limit=limit,
            exclude_ids=exclude_ids,
        )

    def get_persons_with_birthday_on(self, month: int, day: int) -> list[Person]:
        return persons.get_persons_with_birthday_on(self._engine, month, day)

    def search_persons(self, query: str, *, offset: int = 0, limit: int = 3) -> list[Person]:
        return persons.search_persons(self._engine, query, offset=offset, limit=limit)

    def get_person_first_asset_date(self, person_id: UUID) -> date | None:
        return persons.get_person_first_asset_date(self._engine, person_id)

    def get_assets_together_count(self, person_a_id: UUID, person_b_id: UUID) -> int:
        return persons.get_assets_together_count(self._engine, person_a_id, person_b_id)

    def get_top_co_occurring_persons(
        self, person_id: UUID, *, limit: int = 3, exclude_ids: frozenset[UUID] = frozenset()
    ) -> list[tuple[UUID, str, int]]:
        return persons.get_top_co_occurring_persons(self._engine, person_id, limit=limit, exclude_ids=exclude_ids)

    def get_random_asset_with_named_faces(
        self,
        *,
        exclude_asset_ids: frozenset[UUID] = frozenset(),
        exclude_person_ids: frozenset[UUID] = frozenset(),
    ) -> list[Face]:
        return faces.get_random_asset_with_named_faces(
            self._engine, exclude_asset_ids=exclude_asset_ids, exclude_person_ids=exclude_person_ids
        )

    def get_named_persons_in_asset(self, asset_id: UUID) -> list[str]:
        return faces.get_named_persons_in_asset(self._engine, asset_id)

    def get_albums(
        self,
        *,
        ids: frozenset[UUID] | None = None,
        name_query: str | None = None,
        min_asset_count: int | None = None,
        randomize: bool = False,
        asset_count_weight: float | None = None,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Album]:
        return albums.get_albums(
            self._engine,
            ids=ids,
            name_query=name_query,
            min_asset_count=min_asset_count,
            randomize=randomize,
            asset_count_weight=asset_count_weight,
            limit=limit,
            exclude_ids=exclude_ids,
        )

    def search_albums(self, query: str, *, offset: int = 0, limit: int = 3) -> list[Album]:
        return albums.search_albums(self._engine, query, offset=offset, limit=limit)

    def get_album_cover_asset_id(self, album_id: UUID) -> UUID | None:
        return albums.get_album_cover_asset_id(self._engine, album_id)

    def get_album_first_asset_date(self, album_id: UUID) -> date | None:
        return albums.get_album_first_asset_date(self._engine, album_id)

    def get_album_last_asset_date(self, album_id: UUID) -> date | None:
        return albums.get_album_last_asset_date(self._engine, album_id)

    def get_albums_starting_on(self, month: int, day: int) -> list[tuple[UUID, str, date]]:
        return albums.get_albums_starting_on(self._engine, month, day)

    def get_album_named_face_counts(self, album_id: UUID) -> list[tuple[UUID, str, int]]:
        return albums.get_album_named_face_counts(self._engine, album_id)

    def get_persons_present_in_album(self, album_id: UUID, person_ids: frozenset[UUID]) -> frozenset[UUID]:
        return albums.get_persons_present_in_album(self._engine, album_id, person_ids)

    def get_asset_thumbnail(self, asset_id: UUID, size: str = "preview") -> tuple[bytes, str]:
        return images.get_asset_thumbnail(self._settings, asset_id, size)

    def get_person_thumbnail(self, person_id: UUID) -> tuple[bytes, str]:
        return images.get_person_thumbnail(self._settings, person_id)


class ContentQueries(Protocol):
    """The subset of ImmichService's surface that picking a round's content actually needs
    (LiveContent/CandidateProvider classes, and each game's daily.py build_spec) - ImmichService
    satisfies this structurally already. Exists so services/daily_challenge_service.py's cross-day
    exclusion wrapper (_ExcludingImmichService) can be passed anywhere a live game or a build_spec
    expects Immich content queries without erasing the type to Any, even though the wrapper isn't
    (and by design doesn't want to be, see its own docstring) an ImmichService subclass."""

    def get_assets(
        self,
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
        ids: frozenset[UUID] | None = None,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Asset]: ...

    def get_persons(
        self,
        *,
        named_only: bool = True,
        with_birthdate: bool | None = None,
        min_asset_count: int | None = None,
        name_query: str | None = None,
        ids: frozenset[UUID] | None = None,
        randomize: bool = False,
        asset_count_weight: float | None = None,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Person]: ...

    def get_albums(
        self,
        *,
        ids: frozenset[UUID] | None = None,
        name_query: str | None = None,
        min_asset_count: int | None = None,
        randomize: bool = False,
        asset_count_weight: float | None = None,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Album]: ...

    def get_random_asset_with_named_faces(
        self,
        *,
        exclude_asset_ids: frozenset[UUID] = frozenset(),
        exclude_person_ids: frozenset[UUID] = frozenset(),
    ) -> list[Face]: ...

    def get_person_first_asset_date(self, person_id: UUID) -> date | None: ...

    def get_assets_together_count(self, person_a_id: UUID, person_b_id: UUID) -> int: ...

    def get_top_co_occurring_persons(
        self, person_id: UUID, *, limit: int = 3, exclude_ids: frozenset[UUID] = frozenset()
    ) -> list[tuple[UUID, str, int]]: ...

    def get_album_first_asset_date(self, album_id: UUID) -> date | None: ...

    def get_album_named_face_counts(self, album_id: UUID) -> list[tuple[UUID, str, int]]: ...

    def get_persons_present_in_album(self, album_id: UUID, person_ids: frozenset[UUID]) -> frozenset[UUID]: ...
