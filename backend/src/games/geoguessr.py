"""
Based on the Geoguessr game. A single asset with a known location is shown - the player marks a
point on a map guessing where it was taken. 5 rounds are always played (unlike MoreOrLess, a wrong
guess doesn't end the game early), and the final score is the sum of all 5 rounds' scores. See
docs/GAMES/GEOGUESSR.md.
"""

import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from domain.asset import Asset
from games.base import BaseGame, BaseRound
from services.immich_service import ImmichService

GAME_TYPE = "geoguessr"
MODE_DISTANCE_BETWEEN_GUESS = "distanceBetweenGuess"

TOTAL_ROUNDS = 5
MAX_SCORE = 5000
FLAT_SCORE_RADIUS_KM = 1.0
# Beyond the flat-score radius: score = round(MAX_SCORE * exp(-distance_km / DECAY_KM)). Calibrated
# against the dev library's real spread (genuinely worldwide - Chile, Thailand, Italy, etc., several
# thousand km apart) so a decent-but-not-exact guess still scores something: ~1839pts at 2000km,
# ~410pts at 5000km, ~34pts at 10000km.
DECAY_KM = 2000.0
EARTH_RADIUS_KM = 6371.0

# How many random located photos to sample when looking for one far enough from every previous
# round's true location - see _pick_asset. Not required for correctness (falls back to the first
# candidate if none qualifies) - just keeps rounds spread out instead of clustering on the same spot.
_CANDIDATE_SAMPLE_SIZE = 10
_MIN_CANDIDATE_SEPARATION_KM = 50.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _score_for_distance(distance_km: float) -> int:
    if distance_km <= FLAT_SCORE_RADIUS_KM:
        return MAX_SCORE
    return max(0, round(MAX_SCORE * math.exp(-distance_km / DECAY_KM)))


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


def _pick_asset(
    immich_service: ImmichService, exclude_ids: frozenset[UUID], previous_locations: list[tuple[float, float]]
) -> Asset | None:
    """Samples a few random located photos and prefers one far enough from every previous round's
    true location, so rounds don't end up testing near-duplicate spots (the dev library has
    clusters of 15-24 photos at a single location). Falls back to the first candidate if none
    qualifies - mirrors more_or_less.py's _pick_non_tied_candidate."""
    candidates = immich_service.get_assets(
        media_type="photo", with_location=True, random=True, limit=_CANDIDATE_SAMPLE_SIZE, exclude_ids=exclude_ids
    )
    if not candidates:
        return None
    for candidate in candidates:
        if all(
            haversine_km(candidate.latitude, candidate.longitude, lat, lon) >= _MIN_CANDIDATE_SEPARATION_KM
            for lat, lon in previous_locations
        ):
            return candidate
    return candidates[0]


class GeoguessrRound(BaseRound):
    def __init__(self, id: UUID, game_id: UUID, round_index: int, asset: AssetSnapshot) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[asset.id])
        self.asset = asset
        self.guess: LatLng | None = None

    @property
    def distance_km(self) -> float | None:
        if self.guess is None:
            return None
        return haversine_km(self.asset.latitude, self.asset.longitude, self.guess.latitude, self.guess.longitude)

    def calculate_score(self) -> int:
        assert self.distance_km is not None  # BaseGame.play_round already set self.guess
        return _score_for_distance(self.distance_km)

    def to_payload(self) -> dict[str, Any]:
        return {"asset": self.asset.to_dict(), "guess": self.guess.to_dict() if self.guess else None}

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "GeoguessrRound":
        round_ = cls(id=id, game_id=game_id, round_index=round_index, asset=AssetSnapshot.from_dict(payload["asset"]))
        round_.guess = LatLng.from_dict(payload["guess"]) if payload["guess"] else None
        round_.score_delta = score_delta
        return round_


class GeoguessrGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        owner: str,
        rounds: list[GeoguessrRound],
        immich_service: ImmichService,
        score: int = 0,
        finished: bool = False,
    ) -> None:
        super().__init__(
            id=id,
            owner=owner,
            game_type=GAME_TYPE,
            mode=MODE_DISTANCE_BETWEEN_GUESS,
            rounds=rounds,
            score=score,
            finished=finished,
        )
        self._immich_service = immich_service

    @classmethod
    def start(cls, id: UUID, owner: str, immich_service: ImmichService) -> "GeoguessrGame":
        asset = _pick_asset(immich_service, exclude_ids=frozenset(), previous_locations=[])
        if asset is None:
            raise ValueError("not enough located photos in Immich to start a Geoguessr game")

        first_round = GeoguessrRound(id=uuid4(), game_id=id, round_index=1, asset=AssetSnapshot.of(asset))
        return cls(id=id, owner=owner, rounds=[first_round], immich_service=immich_service)

    def _shown_asset_ids(self) -> frozenset[UUID]:
        return frozenset(round_.asset.id for round_ in self.rounds)

    def _previous_locations(self) -> list[tuple[float, float]]:
        return [(round_.asset.latitude, round_.asset.longitude) for round_ in self.rounds]

    def has_next_round(self) -> bool:
        if self.current_round.round_index >= TOTAL_ROUNDS:
            return False
        # Cheap existence check - create_next_round()'s separation-aware pick always succeeds as
        # long as the candidate pool isn't empty (see _pick_asset's fallback), so this is
        # consistent with it without needing to sample _CANDIDATE_SAMPLE_SIZE rows twice.
        remaining = self._immich_service.get_assets(
            media_type="photo", with_location=True, limit=1, exclude_ids=self._shown_asset_ids()
        )
        return bool(remaining)

    def create_next_round(self) -> GeoguessrRound:
        asset = _pick_asset(self._immich_service, self._shown_asset_ids(), self._previous_locations())
        if asset is None:
            raise ValueError("no more located photos left - has_next_round() should have returned False")

        return GeoguessrRound(
            id=uuid4(),
            game_id=self.id,
            round_index=self.current_round.round_index + 1,
            asset=AssetSnapshot.of(asset),
        )
