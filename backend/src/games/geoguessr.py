"""
Based on the Geoguessr game. A single asset with a known location is shown - the player marks a
point on a map guessing where it was taken. 5 rounds are always played (unlike MoreOrLess, a wrong
guess doesn't end the game early), and the final score is the sum of all 5 rounds' scores. See
docs/GAMES/GEOGUESSR.md.

The fixed-rounds game loop (round count, candidate picking, next-round creation, exponential-decay
scoring) lives in games/asset_rounds.py and is shared with Dateguessr - only the location metric
and per-round snapshot are Geoguessr-specific and live here.
"""

import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from domain.asset import Asset
from games.asset_rounds import MAX_SCORE, TOTAL_ROUNDS, AssetRoundsGame, exp_decay_score  # noqa: F401 (MAX_SCORE/TOTAL_ROUNDS re-exported for tests)
from games.base import BaseRound

GAME_TYPE = "geoguessr"
MODE_DISTANCE_BETWEEN_GUESS = "distanceBetweenGuess"

FLAT_SCORE_RADIUS_KM = 1.0
# Beyond the flat-score radius: score = round(MAX_SCORE * exp(-distance_km / DECAY_KM)). Calibrated
# against the dev library's real spread (genuinely worldwide - Chile, Thailand, Italy, etc., several
# thousand km apart) so a decent-but-not-exact guess still scores something: ~1839pts at 2000km,
# ~410pts at 5000km, ~34pts at 10000km.
DECAY_KM = 2000.0
EARTH_RADIUS_KM = 6371.0

# Minimum great-circle distance a new round's asset should keep from every previous round's true
# location, so rounds don't cluster on the same spot (the dev library has clusters of 15-24 photos
# at a single location). Best-effort - see games/asset_rounds.py's pick_spread_asset.
_MIN_CANDIDATE_SEPARATION_KM = 50.0

# How close (great-circle) an extra photo must be to the round's main asset to be shown alongside
# it - see games/asset_rounds.py's MAX_EXTRA_ASSETS.
_EXTRA_RADIUS_KM = 0.5


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class LatLng:
    latitude: float
    longitude: float

    def to_dict(self) -> dict[str, float]:
        return {"latitude": self.latitude, "longitude": self.longitude}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LatLng":
        return cls(latitude=data["latitude"], longitude=data["longitude"])


@dataclass(frozen=True)
class AssetSnapshot:
    """An asset's id/location frozen at the moment a round was created - not a live query result,
    so a round's answer stays stable even if the underlying Immich data changes later (same
    rationale as more_or_less.py's PersonSnapshot)."""

    id: UUID
    latitude: float
    longitude: float

    @classmethod
    def of(cls, asset: Asset) -> "AssetSnapshot":
        if asset.latitude is None or asset.longitude is None:
            raise ValueError(f"asset {asset.id} has no location")
        return cls(id=asset.id, latitude=asset.latitude, longitude=asset.longitude)

    def to_dict(self) -> dict[str, Any]:
        return {"id": str(self.id), "latitude": self.latitude, "longitude": self.longitude}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetSnapshot":
        return cls(id=UUID(data["id"]), latitude=data["latitude"], longitude=data["longitude"])


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

    def calculate_score(self) -> int:
        assert self.distance_km is not None  # BaseGame.play_round already set self.guess
        return exp_decay_score(self.distance_km, FLAT_SCORE_RADIUS_KM, DECAY_KM)

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


class GeoguessrGame(AssetRoundsGame):
    game_type = GAME_TYPE
    mode = MODE_DISTANCE_BETWEEN_GUESS
    _min_separation = _MIN_CANDIDATE_SEPARATION_KM
    _not_enough_assets_message = "not enough located photos in Immich to start a Geoguessr game"

    def _query_assets(self, exclude_ids: frozenset[UUID], *, limit: int, random: bool) -> list[Asset]:
        return self._immich_service.get_assets(
            media_type="photo", with_location=True, random=random, limit=limit, exclude_ids=exclude_ids
        )

    def _query_extra_assets(self, main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        assert main.latitude is not None and main.longitude is not None
        candidates = self._immich_service.get_assets(
            media_type="photo",
            with_location=True,
            near_km=(main.latitude, main.longitude, _EXTRA_RADIUS_KM),
            local_month=main.local_date.month,
            random=True,
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

    def _make_round(self, round_index: int, asset: Asset, extras: list[Asset]) -> GeoguessrRound:
        return GeoguessrRound(
            id=uuid4(),
            game_id=self.id,
            round_index=round_index,
            asset=AssetSnapshot.of(asset),
            extras=[AssetSnapshot.of(extra) for extra in extras],
        )

    def _separation(self, candidate: Asset, answer: tuple[float, float]) -> float:
        assert candidate.latitude is not None and candidate.longitude is not None
        return haversine_km(candidate.latitude, candidate.longitude, answer[0], answer[1])

    def _previous_answers(self) -> list[tuple[float, float]]:
        return [(round_.asset.latitude, round_.asset.longitude) for round_ in self.rounds]
