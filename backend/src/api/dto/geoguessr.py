"""Geoguessr's request/response DTOs - see api/dto/__init__.py."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import LatLng, GeoguessrRound


class GeoguessrRoundOut(BaseModel):
    game_type: Literal["geoguessr"] = GEOGUESSR_TYPE
    id: UUID
    round_index: int
    # Main ("answer") asset first, then up to 4 decorative extras - see games/asset_rounds.py's
    # MAX_EXTRA_ASSETS. The guess/actual/score fields below are always about the main asset only.
    asset_ids: list[UUID]
    guess_latitude: float | None
    guess_longitude: float | None
    # Redacted (null) until this round has been answered - same rationale as
    # MoreOrLessRoundOut.candidate_asset_count.
    actual_latitude: float | None
    actual_longitude: float | None
    distance_km: float | None
    score_delta: int | None

    @classmethod
    def from_round(cls, round_: GeoguessrRound) -> "GeoguessrRoundOut":
        answered = round_.answered
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            asset_ids=[round_.asset.id] + [extra.id for extra in round_.extras],
            guess_latitude=round_.guess.latitude if round_.guess else None,
            guess_longitude=round_.guess.longitude if round_.guess else None,
            actual_latitude=round_.asset.latitude if answered else None,
            actual_longitude=round_.asset.longitude if answered else None,
            distance_km=round(round_.distance_km, 3) if answered else None,
            score_delta=round_.score_delta if answered else None,
        )


class GeoguessrPlayRoundIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    def to_domain(self) -> LatLng:
        return LatLng(latitude=self.latitude, longitude=self.longitude)
