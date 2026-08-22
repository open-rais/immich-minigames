"""Shared base for the two ContentQueries-wrapping "skip these ids when sampling" services -
services/daily_challenge_service.py's _ExcludingImmichService (the cross-day no-repeat window) and
services/reports_service.py's _ReportsExcludingImmichService (open-report exclusion). Composition,
not a subclass of ImmichService - satisfies ContentQueries structurally (a Protocol doesn't need a
subclass relationship), which is what lets either wrapper stand in for a real ImmichService without
widening the type to Any. Only the query methods any game's build_spec()/live round generation
actually calls are overridden here; everything else (thumbnail fetches, person search, per-id clue
queries) is forwarded straight through via __getattr__.

What differs between the two wrappers is injected, not duplicated per subclass:

- The four `_*_exclusion()` hooks say *which* ids to add for each query dimension - a flat
  same-value-everywhere set for the no-repeat window (it doesn't distinguish entity kind), a
  per-kind ReportExclusions breakdown for reports. `_named_face_person_exclusion` is its own hook,
  not reused from `_person_exclusion`, because the two mean different things: the latter widens
  `get_persons`' sampling exclusion, the former widens `get_random_asset_with_named_faces`'
  `exclude_person_ids` - excluding a specific person's *face* from an otherwise-eligible asset, a
  concept the no-repeat window never uses (it stays empty for that wrapper).
- `retry_without_exclusion`: whether an empty result *because of* this wrapper's own exclusion
  should retry once unfiltered - False for the no-repeat window (an empty pool there is real
  content exhaustion, handled by DailyChallengeService's own outer retry-with-no-exclusion-at-all
  instead), True for reports (a report is a best-effort nudge, not a hard guarantee that could
  otherwise stall a game mid-run just because its whole remaining pool happens to be reported).
- `bypass_on_explicit_ids`: whether `ids=` (resolving a concrete id, e.g. a guess lookup) skips
  exclusion entirely - True for reports (a reported entity must stay guessable/searchable even
  while excluded from being the thing to guess), False for the no-repeat window (it has no such
  case to handle - nothing calls it with `ids=` set).

Composes: daily_challenge_service.py wraps a _ReportsExcludingImmichService around a
_ExcludingImmichService (see DailyChallengeService._build_spec's own comment on why the no-repeat
window has to be the *inner* one), which only works because both satisfy the exact same
ContentQueries shape - this base is what guarantees that."""

from typing import Any
from uuid import UUID


class ExcludingContentQueries:
    def __init__(self, inner: Any, *, retry_without_exclusion: bool, bypass_on_explicit_ids: bool) -> None:
        self._inner = inner
        self._retry_without_exclusion = retry_without_exclusion
        self._bypass_on_explicit_ids = bypass_on_explicit_ids

    def _asset_exclusion(self) -> frozenset[UUID]:
        return frozenset()

    def _person_exclusion(self) -> frozenset[UUID]:
        return frozenset()

    def _album_exclusion(self) -> frozenset[UUID]:
        return frozenset()

    def _named_face_person_exclusion(self) -> frozenset[UUID]:
        return frozenset()

    def get_assets(
        self, *, ids: frozenset[UUID] | None = None, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        if ids is not None and self._bypass_on_explicit_ids:
            return self._inner.get_assets(ids=ids, exclude_ids=exclude_ids, **kwargs)
        extra = self._asset_exclusion()
        result = self._inner.get_assets(ids=ids, exclude_ids=exclude_ids | extra, **kwargs)
        if not result and extra and self._retry_without_exclusion:
            result = self._inner.get_assets(ids=ids, exclude_ids=exclude_ids, **kwargs)
        return result

    def get_persons(
        self, *, ids: frozenset[UUID] | None = None, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        if ids is not None and self._bypass_on_explicit_ids:
            return self._inner.get_persons(ids=ids, exclude_ids=exclude_ids, **kwargs)
        extra = self._person_exclusion()
        result = self._inner.get_persons(ids=ids, exclude_ids=exclude_ids | extra, **kwargs)
        if not result and extra and self._retry_without_exclusion:
            result = self._inner.get_persons(ids=ids, exclude_ids=exclude_ids, **kwargs)
        return result

    def get_albums(
        self, *, ids: frozenset[UUID] | None = None, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        if ids is not None and self._bypass_on_explicit_ids:
            return self._inner.get_albums(ids=ids, exclude_ids=exclude_ids, **kwargs)
        extra = self._album_exclusion()
        result = self._inner.get_albums(ids=ids, exclude_ids=exclude_ids | extra, **kwargs)
        if not result and extra and self._retry_without_exclusion:
            result = self._inner.get_albums(ids=ids, exclude_ids=exclude_ids, **kwargs)
        return result

    def get_random_asset_with_named_faces(
        self, *, exclude_asset_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        extra_assets = self._asset_exclusion()
        extra_persons = self._named_face_person_exclusion()
        result = self._inner.get_random_asset_with_named_faces(
            exclude_asset_ids=exclude_asset_ids | extra_assets, exclude_person_ids=extra_persons, **kwargs
        )
        if not result and (extra_assets or extra_persons) and self._retry_without_exclusion:
            result = self._inner.get_random_asset_with_named_faces(exclude_asset_ids=exclude_asset_ids, **kwargs)
        return result

    def has_named_faces_asset(self, *, exclude_asset_ids: frozenset[UUID] = frozenset(), **kwargs: Any) -> Any:
        extra_assets = self._asset_exclusion()
        extra_persons = self._named_face_person_exclusion()
        result = self._inner.has_named_faces_asset(
            exclude_asset_ids=exclude_asset_ids | extra_assets, exclude_person_ids=extra_persons, **kwargs
        )
        if not result and (extra_assets or extra_persons) and self._retry_without_exclusion:
            result = self._inner.has_named_faces_asset(exclude_asset_ids=exclude_asset_ids, **kwargs)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
