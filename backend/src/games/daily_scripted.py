"""
Roadmap #G (daily games) - thin subclasses that replay a pre-generated `daily_challenges.spec`
(services/daily_service.py) instead of querying Immich live, for the three games whose engine
doesn't already have a provider-style seam (MoreOrLess has ScriptedCandidateProvider in
games/more_or_less.py; Immichdle just takes an optional `target` in ImmichdleGame.start()).

Each subclass overrides only its own game's "which content comes next" hook - Geoguessr/Dateguessr
share AssetRoundsGame's `_pick_asset`/`_pick_extras`, WhosThatPerson has its own `_pick_round_content`
(added specifically for this) - plus the existence-check half of `has_next_round`. Scoring, streaks,
round-count bookkeeping, and everything else stay inherited untouched.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from domain.asset import Asset
from games.dateguessr import AssetSnapshot as DateguessrAssetSnapshot
from games.dateguessr import DateguessrGame
from games.geoguessr import AssetSnapshot as GeoguessrAssetSnapshot
from games.geoguessr import GeoguessrGame
from games.whos_that_person import HiddenFace, WhosThatPersonGame, WhosThatPersonRound


def _placeholder_asset(
    id: UUID, *, latitude: float | None = None, longitude: float | None = None, local_date: date | None = None
) -> Asset:
    """A minimal, otherwise-unused Asset carrying only the field(s) AssetSnapshot.of() actually
    reads (id + latitude/longitude for Geoguessr, id + local_date for Dateguessr) - the daily
    subclasses below already know the real snapshot content directly (from the spec), so this only
    exists to satisfy AssetRoundsGame's _pick_asset/_pick_extras -> _make_round pipeline, which is
    typed around the domain Asset the *real* game queries Immich for."""
    return Asset(
        id=id,
        type="IMAGE",
        file_created_at=datetime.min,
        local_date=local_date or date.min,
        original_file_name="",
        width=None,
        height=None,
        is_favorite=False,
        latitude=latitude,
        longitude=longitude,
        city=None,
        state=None,
        country=None,
    )


class DailyGeoguessrGame(GeoguessrGame):
    def __init__(self, *args: Any, rounds_spec: list[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._rounds_spec = rounds_spec

    @classmethod
    def start(  # type: ignore[override]
        cls,
        id: UUID,
        owner: str,
        immich_service: Any,
        settings: Any = None,
        rounds_spec: list[dict[str, Any]] | None = None,
    ) -> "DailyGeoguessrGame":
        # AssetRoundsGame.start() (inherited otherwise) constructs `cls(...)` without knowing about
        # rounds_spec - overridden here just to thread it through the constructor; the pick/build
        # sequence itself is identical to the base class's.
        game = cls(
            id=id, owner=owner, rounds=[], immich_service=immich_service, settings=settings, rounds_spec=rounds_spec or []
        )
        asset = game._pick_asset(exclude_ids=frozenset())
        if asset is None:
            raise ValueError(cls._not_enough_assets_message)
        extras = game._pick_extras(asset, exclude_ids=frozenset({asset.id}))
        game.rounds.append(game._make_round(round_index=1, asset=asset, extras=extras))
        return game

    def _spec_index(self) -> int:
        # See games/daily_service.py's _build_asset_rounds_spec docstring reasoning - _pick_asset
        # and _pick_extras are both called (in that order) before self.rounds grows, both from
        # start() and create_next_round(), so len(self.rounds) is a stable "which spec round is
        # being built right now" index across both hooks.
        return len(self.rounds)

    def _pick_asset(self, exclude_ids: frozenset[UUID]) -> Asset | None:
        idx = self._spec_index()
        if idx >= len(self._rounds_spec):
            return None
        snapshot = GeoguessrAssetSnapshot.from_dict(self._rounds_spec[idx]["main"])
        return _placeholder_asset(snapshot.id, latitude=snapshot.latitude, longitude=snapshot.longitude)

    def _pick_extras(self, main: Asset, exclude_ids: frozenset[UUID]) -> list[Asset]:
        idx = self._spec_index()
        if idx >= len(self._rounds_spec):
            return []
        extras = [GeoguessrAssetSnapshot.from_dict(e) for e in self._rounds_spec[idx]["extras"]]
        return [_placeholder_asset(e.id, latitude=e.latitude, longitude=e.longitude) for e in extras]

    def has_next_round(self) -> bool:
        if self.current_round.round_index >= self.total_rounds:
            return False
        return self._spec_index() < len(self._rounds_spec)


class DailyDateguessrGame(DateguessrGame):
    def __init__(self, *args: Any, rounds_spec: list[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._rounds_spec = rounds_spec

    @classmethod
    def start(  # type: ignore[override]
        cls,
        id: UUID,
        owner: str,
        immich_service: Any,
        settings: Any = None,
        rounds_spec: list[dict[str, Any]] | None = None,
    ) -> "DailyDateguessrGame":
        game = cls(
            id=id, owner=owner, rounds=[], immich_service=immich_service, settings=settings, rounds_spec=rounds_spec or []
        )
        asset = game._pick_asset(exclude_ids=frozenset())
        if asset is None:
            raise ValueError(cls._not_enough_assets_message)
        extras = game._pick_extras(asset, exclude_ids=frozenset({asset.id}))
        game.rounds.append(game._make_round(round_index=1, asset=asset, extras=extras))
        return game

    def _spec_index(self) -> int:
        return len(self.rounds)

    def _pick_asset(self, exclude_ids: frozenset[UUID]) -> Asset | None:
        idx = self._spec_index()
        if idx >= len(self._rounds_spec):
            return None
        snapshot = DateguessrAssetSnapshot.from_dict(self._rounds_spec[idx]["main"])
        return _placeholder_asset(snapshot.id, local_date=snapshot.date)

    def _pick_extras(self, main: Asset, exclude_ids: frozenset[UUID]) -> list[Asset]:
        idx = self._spec_index()
        if idx >= len(self._rounds_spec):
            return []
        extras = [DateguessrAssetSnapshot.from_dict(e) for e in self._rounds_spec[idx]["extras"]]
        return [_placeholder_asset(e.id, local_date=e.date) for e in extras]

    def has_next_round(self) -> bool:
        if self.current_round.round_index >= self.total_rounds:
            return False
        return self._spec_index() < len(self._rounds_spec)


class DailyWhosThatPersonGame(WhosThatPersonGame):
    def __init__(self, *args: Any, rounds_spec: list[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._rounds_spec = rounds_spec

    @classmethod
    def start(  # type: ignore[override]
        cls,
        id: UUID,
        owner: str,
        immich_service: Any,
        settings: Any = None,
        rounds_spec: list[dict[str, Any]] | None = None,
    ) -> "DailyWhosThatPersonGame":
        # WhosThatPersonGame.start() (inherited otherwise) constructs `cls(...)` without knowing
        # about rounds_spec - overridden here just to thread it through, same reasoning as
        # DailyGeoguessrGame/DailyDateguessrGame.start() above.
        game = cls(
            id=id, owner=owner, rounds=[], immich_service=immich_service, settings=settings, rounds_spec=rounds_spec or []
        )
        picked = game._pick_round_content(min(game._max_hidden_faces, game.total_people), frozenset())
        if picked is None:
            raise ValueError("not enough named faces in the daily spec to start a Who'sThatPerson game")
        asset_id, faces = picked
        first_round = WhosThatPersonRound(id=uuid4(), game_id=id, round_index=1, asset_id=asset_id, faces=faces)
        game.rounds.append(first_round)
        return game

    def _pick_round_content(
        self, max_faces: int, exclude_asset_ids: frozenset[UUID]
    ) -> tuple[UUID, list[HiddenFace]] | None:
        # max_faces/exclude_asset_ids are ignored - the spec already froze exactly which asset and
        # faces belong to this round at generation time (games/daily_service.py's
        # _build_whos_that_person_spec).
        idx = len(self.rounds)
        if idx >= len(self._rounds_spec):
            return None
        round_spec = self._rounds_spec[idx]
        return UUID(round_spec["asset_id"]), [HiddenFace.from_dict(f) for f in round_spec["faces"]]
