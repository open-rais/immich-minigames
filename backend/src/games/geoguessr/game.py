"""
Based on the Geoguessr game. A single asset with a known location is shown - the player marks a
point on a map guessing where it was taken. 5 rounds are always played (unlike MoreOrLess, a wrong
guess doesn't end the game early), and the final score is the sum of all 5 rounds' scores. See
docs/GAMES/GEOGUESSR.md.

Owns its entire game loop (round count, next-round creation, exponential-decay scoring) -
previously factored out into a shared base class with Dateguessr (games/asset_rounds.py),
deliberately un-shared per docs/TODO/DECOUPLING.md so a change to this game's loop never requires
touching Dateguessr's. *Which* asset/extras a round gets is a separate axis of variation
(`GeoguessrContent` below) - live Immich queries normally, a frozen daily spec for the daily flow
(games/geoguessr/daily.py's ScriptedContent) - mirroring how MoreOrLess already varies its content
via CandidateProvider.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from domain.asset import Asset
from games.base import BaseGame, BaseRound
from games.shared.picking import pick_spread_asset
from games.shared.scoring import exp_decay_score
from games.shared.serialization import DictCodec
from services.immich_service import ImmichService

GAME_TYPE = "geoguessr"
MODE_DISTANCE_BETWEEN_GUESS = "distanceBetweenGuess"

TOTAL_ROUNDS = 5
MAX_SCORE = 5000
FLAT_SCORE_RADIUS_KM = 1.0
DECAY_KM = 1500.0
EARTH_RADIUS_KM = 6371.0

# How many random photos to sample when looking for one far enough from every previous round's
# answer - see games/shared/picking.py's pick_spread_asset. Not required for correctness (falls
# back to the first candidate if none qualifies) - just keeps rounds spread out instead of
# clustering on near-duplicate answers.
_CANDIDATE_SAMPLE_SIZE = 10

# Up to this many additional photos are shown alongside a round's main asset (purely decorative -
# the round's answer/score always stay tied to the main asset only). Fewer are shown if fewer
# qualify - a round is never forced to have exactly 5.
MAX_EXTRA_ASSETS = 4
# How many random candidates to sample when looking for extras - mirrors _CANDIDATE_SAMPLE_SIZE's
# rationale, just sized a bit larger since up to MAX_EXTRA_ASSETS of them are kept at once instead
# of just one.
_EXTRA_CANDIDATE_SAMPLE_SIZE = 10

# Minimum great-circle distance a new round's asset should keep from every previous round's true
# location, so rounds don't cluster on the same spot (the dev library has clusters of 15-24 photos
# at a single location). Best-effort - see games/shared/picking.py's pick_spread_asset.
_MIN_CANDIDATE_SEPARATION_KM = 50.0

# How close (great-circle) an extra photo must be to the round's main asset to be shown alongside
# it - see MAX_EXTRA_ASSETS.
_EXTRA_RADIUS_KM = 0.5


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class LatLng(DictCodec):
    latitude: float
    longitude: float


@dataclass(frozen=True)
class AssetSnapshot(DictCodec):
    """An asset's id/location frozen at the moment a round was created - not a live query result,
    so a round's answer stays stable even if the underlying Immich data changes later (same
    rationale as more_or_less.py's EntitySnapshot)."""

    id: UUID
    latitude: float
    longitude: float

    @classmethod
    def of(cls, asset: Asset) -> "AssetSnapshot":
        if asset.latitude is None or asset.longitude is None:
            raise ValueError(f"asset {asset.id} has no location")
        return cls(id=asset.id, latitude=asset.latitude, longitude=asset.longitude)


class GeoguessrContent(Protocol):
    """The single point of variation between a normal Geoguessr game and a daily one (roadmap #G) -
    live Immich queries (LiveContent below) vs. a frozen daily spec (games/geoguessr/daily.py's
    ScriptedContent). The game engine below never knows which."""

    @staticmethod
    def pick_asset(exclude_ids: frozenset[UUID], previous_answers: list[tuple[float, float]]) -> Asset | None:
        """The next round's main asset, excluding `exclude_ids` and preferring one far enough from
        every entry in `previous_answers` (see games/shared/picking.py's pick_spread_asset) - None
        when no eligible asset is left."""
        ...

    @staticmethod
    def pick_extras(main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        """Up to `limit` decorative photos to show alongside `main` this round."""
        ...

    @staticmethod
    def has_more(exclude_ids: frozenset[UUID]) -> bool:
        """Whether another round's worth of content is available, without actually picking it -
        used by has_next_round() so it doesn't have to look at a guess to decide (this game's
        rounds are guess-independent, unlike MoreOrLess's chain)."""
        ...


class LiveContent:
    """Normal-play GeoguessrContent - samples eligible assets straight from Immich."""

    def __init__(self, immich_service: ImmichService) -> None:
        self._immich_service = immich_service

    def _query_assets(self, exclude_ids: frozenset[UUID], *, limit: int, randomize: bool) -> list[Asset]:
        return self._immich_service.get_assets(
            media_type="photo", with_location=True, randomize=randomize, limit=limit, exclude_ids=exclude_ids
        )

    def _query_extra_assets(self, main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        assert main.latitude is not None and main.longitude is not None
        candidates = self._immich_service.get_assets(
            media_type="photo",
            with_location=True,
            near_km=(main.latitude, main.longitude, _EXTRA_RADIUS_KM),
            local_month=main.local_date.month,
            randomize=True,
            limit=limit,
            exclude_ids=exclude_ids,
        )
        # near_km is a coarse bounding-box prefilter (box, not circle) - keep only the ones that are
        # truly within the radius.
        kept = []
        for candidate in candidates:
            assert candidate.latitude is not None and candidate.longitude is not None  # with_location=True
            if haversine_km(main.latitude, main.longitude, candidate.latitude, candidate.longitude) <= _EXTRA_RADIUS_KM:
                kept.append(candidate)
        return kept

    @staticmethod
    def _separation(candidate: Asset, answer: tuple[float, float]) -> float:
        assert candidate.latitude is not None and candidate.longitude is not None
        return haversine_km(candidate.latitude, candidate.longitude, answer[0], answer[1])

    def pick_asset(self, exclude_ids: frozenset[UUID], previous_answers: list[tuple[float, float]]) -> Asset | None:
        candidates = self._query_assets(exclude_ids, limit=_CANDIDATE_SAMPLE_SIZE, randomize=True)
        return pick_spread_asset(candidates, previous_answers, self._separation, _MIN_CANDIDATE_SEPARATION_KM)

    def pick_extras(self, main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        candidates = self._query_extra_assets(main, exclude_ids, limit=_EXTRA_CANDIDATE_SAMPLE_SIZE)
        return candidates[:limit]

    def has_more(self, exclude_ids: frozenset[UUID]) -> bool:
        # Cheap existence check - pick_asset()'s separation-aware pick always succeeds as long as
        # the candidate pool isn't empty (see pick_spread_asset's fallback), so this is consistent
        # with it without needing to sample _CANDIDATE_SAMPLE_SIZE rows twice.
        return bool(self._query_assets(exclude_ids, limit=1, randomize=False))


class GeoguessrRound(BaseRound):
    def __init__(
        self,
        id: UUID,
        game_id: UUID,
        round_index: int,
        asset: AssetSnapshot,
        extras: list[AssetSnapshot] | None = None,
    ) -> None:
        extras = extras or []
        super().__init__(id, game_id, round_index, shown_entities=[asset.id] + [extra.id for extra in extras])
        self.asset = asset
        self.extras = extras
        self.guess: LatLng | None = None

    @property
    def distance_km(self) -> float | None:
        if self.guess is None:
            return None
        return haversine_km(self.asset.latitude, self.asset.longitude, self.guess.latitude, self.guess.longitude)

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        if self.distance_km is None:
            raise RuntimeError("calculate_score() called before BaseGame.play_round set self.guess")
        settings = settings or {}
        flat_zone = settings.get("flat_score_radius_km", FLAT_SCORE_RADIUS_KM)
        decay = settings.get("decay_km", DECAY_KM)
        max_score = int(settings.get("max_score", MAX_SCORE))
        return exp_decay_score(self.distance_km, flat_zone, decay, max_score)

    def to_payload(self) -> dict[str, Any]:
        return {
            "asset": self.asset.to_dict(),
            "extras": [extra.to_dict() for extra in self.extras],
            "guess": self.guess.to_dict() if self.guess else None,
        }

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "GeoguessrRound":
        round_ = cls(
            id=id,
            game_id=game_id,
            round_index=round_index,
            asset=AssetSnapshot.from_dict(payload["asset"]),
            extras=[AssetSnapshot.from_dict(extra) for extra in payload.get("extras", [])],
        )
        round_.guess = LatLng.from_dict(payload["guess"]) if payload["guess"] else None
        round_.score_delta = score_delta
        return round_


class GeoguessrGame(BaseGame):
    game_type = GAME_TYPE
    mode = MODE_DISTANCE_BETWEEN_GUESS
    _not_enough_assets_message = "not enough located photos in Immich to start a Geoguessr game"

    def __init__(
        self,
        id: UUID,
        rounds: list[BaseRound],
        content: GeoguessrContent,
        score: int = 0,
        finished: bool = False,
        settings: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            game_type=self.game_type,
            mode=self.mode,
            rounds=rounds,
            score=score,
            finished=finished,
            settings=settings,
        )
        self._content = content

    # -- admin-configurable (ADMIN-FEATURE.md point #4, see services/game_settings.py) ----------

    @property
    def total_rounds(self) -> int:
        # Public (no leading underscore) - api/dto/common.py's GameOut reads this to show the
        # frontend the *live* round count instead of the hardcoded display-only constant it used to
        # mirror.
        return int(self._settings.get("total_rounds", TOTAL_ROUNDS))

    @property
    def _max_extra_assets(self) -> int:
        return int(self._settings.get("max_extra_assets", MAX_EXTRA_ASSETS))

    # -- round building -------------------------------------------------------

    def _make_round(self, round_index: int, asset: Asset, extras: list[Asset]) -> GeoguessrRound:
        return GeoguessrRound(
            id=uuid4(),
            game_id=self.id,
            round_index=round_index,
            asset=AssetSnapshot.of(asset),
            extras=[AssetSnapshot.of(extra) for extra in extras],
        )

    def _previous_answers(self) -> list[tuple[float, float]]:
        return [(round_.asset.latitude, round_.asset.longitude) for round_ in self.rounds]

    # -- game loop ------------------------------------------------------------

    @property
    def _shown_asset_ids(self) -> frozenset[UUID]:
        # Flattens every round's shown_entities (main asset + its extras), so an asset already shown
        # this game - whether as a main asset or just as an extra - is never picked again as either.
        return frozenset(id_ for round_ in self.rounds for id_ in round_.shown_entities)

    def _pick_asset(self, exclude_ids: frozenset[UUID]) -> Asset | None:
        return self._content.pick_asset(exclude_ids, self._previous_answers())

    def _pick_extras(self, main: Asset, exclude_ids: frozenset[UUID]) -> list[Asset]:
        return self._content.pick_extras(main, exclude_ids, limit=self._max_extra_assets)

    @classmethod
    def start(
        cls, id: UUID, content: GeoguessrContent, settings: Mapping[str, float] | None = None
    ) -> "GeoguessrGame":
        game = cls(id=id, rounds=[], content=content, settings=settings)
        asset = game._pick_asset(exclude_ids=frozenset())
        if asset is None:
            raise ValueError(cls._not_enough_assets_message)
        extras = game._pick_extras(asset, exclude_ids=frozenset({asset.id}))
        game.rounds.append(game._make_round(round_index=1, asset=asset, extras=extras))
        return game

    def has_next_round(self) -> bool:
        if self.current_round.round_index >= self.total_rounds:
            return False
        return self._content.has_more(self._shown_asset_ids)

    def create_next_round(self) -> BaseRound:
        asset = self._pick_asset(self._shown_asset_ids)
        if asset is None:
            raise ValueError("no more eligible assets left - has_next_round() should have returned False")
        extras = self._pick_extras(asset, exclude_ids=self._shown_asset_ids | {asset.id})
        return self._make_round(round_index=self.current_round.round_index + 1, asset=asset, extras=extras)
