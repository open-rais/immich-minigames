"""GeoguessrRound - a single placed-guess round, its frozen answer snapshot, and the distance/
scoring math that only the round itself needs. See games/geoguessr/game.py for the loop that
drives rounds and games/geoguessr/content.py for where a round's asset comes from."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from domain.asset import Asset
from games.base import BaseRound
from games.shared.scoring import exp_decay_score
from games.shared.serialization import DictCodec

MAX_SCORE = 5000
FLAT_SCORE_RADIUS_KM = 1.0
DECAY_KM = 1500.0
EARTH_RADIUS_KM = 6371.0


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
