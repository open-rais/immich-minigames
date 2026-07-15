"""Dateguessr's request/response DTOs - see api/dto/__init__.py."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import DateguessrRound


class DateguessrRoundOut(BaseModel):
    game_type: Literal["dateguessr"] = DATEGUESSR_TYPE
    id: UUID
    round_index: int
    # Main ("answer") asset first, then up to 4 decorative extras - see
    # GeoguessrRoundOut.asset_ids.
    asset_ids: list[UUID]
    guess_date: date | None
    # Redacted (null) until this round has been answered - same rationale as
    # GeoguessrRoundOut.actual_latitude.
    actual_date: date | None
    days_off: int | None
    score_delta: int | None

    @classmethod
    def from_round(cls, round_: DateguessrRound) -> "DateguessrRoundOut":
        answered = round_.answered
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            asset_ids=[round_.asset.id] + [extra.id for extra in round_.extras],
            guess_date=round_.guess,
            actual_date=round_.asset.date if answered else None,
            days_off=round_.days_off if answered else None,
            score_delta=round_.score_delta if answered else None,
        )


class DateguessrPlayRoundIn(BaseModel):
    date: date

    def to_domain(self) -> date:
        return self.date
