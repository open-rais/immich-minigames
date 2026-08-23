"""Wraps a live ContentQueries with in-memory pools/memos for one Trivium daily build_spec run
(games/trivium/daily.py) - build_spec drives create_next_round() chain_length times, and unlike
every other game Trivium has no shared provider behind its question types
(games/trivium/questions/), so each of those calls re-queries Immich from scratch. Composition +
__getattr__ passthrough, the same shape as services/excluding_content_queries.py's
ExcludingContentQueries (this repo's only wrapper precedent for ContentQueries) - only the methods
Trivium's question types actually call are overridden here, everything else forwards straight
through.

Only used by build_spec, never a live round - a single round gains nothing from pooling, and a
pool that outlived the request would go stale. `inner` may itself already be an exclusion wrapper
(daily's cross-day no-repeat window / reports exclusion, see
services/daily_challenge_service.py::DailyChallengeService._build_spec) - the pool-building calls
below deliberately pass no `exclude_ids` of their own, so whatever permanent exclusion `inner`
applies gets baked into the pool exactly once instead of being lost."""

import random
from datetime import date
from uuid import UUID

from domain.asset import Asset
from domain.person import Person
from games.trivium.questions._shared import LIBRARY_SAMPLE_LIMIT
from services.immich import ContentQueries, LocationField, MediaType


class PooledContentQueries:
    def __init__(self, inner: ContentQueries) -> None:
        self._inner = inner
        self._person_pools: dict[tuple[bool, bool | None], list[Person]] = {}
        self._asset_pools: dict[tuple[MediaType, bool | None], list[Asset]] = {}
        self._co_occurring_cache: dict[tuple[UUID, int], list[tuple[UUID, str, int]]] = {}
        self._first_asset_date_cache: dict[UUID, date | None] = {}
        self._distinct_locations_cache: dict[LocationField, list[str]] = {}

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
        # Point lookups and filter shapes no current Trivium question type uses - pooling them
        # would need per-argument cache keys the pool below isn't shaped for, so they stay live.
        if ids is not None or name_query or min_asset_count is not None or asset_count_weight:
            return self._inner.get_persons(
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
        key = (named_only, with_birthdate)
        pool = self._person_pools.get(key)
        if pool is None:
            pool = self._inner.get_persons(
                named_only=named_only, with_birthdate=with_birthdate, limit=LIBRARY_SAMPLE_LIMIT, randomize=False
            )
            self._person_pools[key] = pool
        eligible = [p for p in pool if p.id not in exclude_ids]
        if randomize:
            return random.sample(eligible, min(limit, len(eligible)))
        return eligible[:limit]

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
        # ids= is a point lookup (games/trivium/questions/_location_shared.py's
        # _previous_values), never a sample - never served from the pool. Same for any date/geo
        # filter, none of which Trivium's location question type ever sets.
        if ids is not None or date_from or date_to or local_date or local_month is not None or near_km is not None:
            return self._inner.get_assets(
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
        key = (media_type, with_location)
        pool = self._asset_pools.get(key)
        if pool is None:
            pool = self._inner.get_assets(
                media_type=media_type, with_location=with_location, limit=LIBRARY_SAMPLE_LIMIT, randomize=False
            )
            self._asset_pools[key] = pool
        eligible = [a for a in pool if a.id not in exclude_ids]
        if randomize:
            return random.sample(eligible, min(limit, len(eligible)))
        return eligible[:limit]

    def get_top_co_occurring_persons(
        self, person_id: UUID, *, limit: int = 3, exclude_ids: frozenset[UUID] = frozenset()
    ) -> list[tuple[UUID, str, int]]:
        # No current caller passes exclude_ids here, but a stale cache entry computed against a
        # different exclusion would be wrong, so this stays live rather than risk it.
        if exclude_ids:
            return self._inner.get_top_co_occurring_persons(person_id, limit=limit, exclude_ids=exclude_ids)
        key = (person_id, limit)
        if key not in self._co_occurring_cache:
            self._co_occurring_cache[key] = self._inner.get_top_co_occurring_persons(person_id, limit=limit)
        return self._co_occurring_cache[key]

    def get_person_first_asset_date(self, person_id: UUID) -> date | None:
        if person_id not in self._first_asset_date_cache:
            self._first_asset_date_cache[person_id] = self._inner.get_person_first_asset_date(person_id)
        return self._first_asset_date_cache[person_id]

    def get_distinct_locations(self, field: LocationField) -> list[str]:
        if field not in self._distinct_locations_cache:
            self._distinct_locations_cache[field] = self._inner.get_distinct_locations(field)
        return self._distinct_locations_cache[field]

    def __getattr__(self, name: str):
        return getattr(self._inner, name)
