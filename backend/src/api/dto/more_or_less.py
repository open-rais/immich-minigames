"""MoreOrLess's request/response DTOs - see api/dto/__init__.py."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MoreOrLessRound


class MoreOrLessRoundOut(BaseModel):
    game_type: Literal["more-or-less"] = MORE_OR_LESS_TYPE
    id: UUID
    round_index: int
    reference_id: UUID
    reference_name: str
    reference_asset_count: int
    candidate_id: UUID
    candidate_name: str
    # Redacted (null) until this round has been answered - otherwise the correct answer could be
    # read straight out of the HTTP response before guessing.
    candidate_asset_count: int | None
    guess: Literal["more", "less"] | None
    correct: bool | None

    @classmethod
    def from_round(cls, round_: MoreOrLessRound) -> "MoreOrLessRoundOut":
        answered = round_.answered
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            reference_id=round_.reference.id,
            reference_name=round_.reference.name,
            reference_asset_count=round_.reference.asset_count,
            candidate_id=round_.candidate.id,
            candidate_name=round_.candidate.name,
            candidate_asset_count=round_.candidate.asset_count if answered else None,
            guess=round_.guess if answered else None,
            correct=round_.correct,
        )


class MoreOrLessPlayRoundIn(BaseModel):
    guess: Literal["more", "less"]

    def to_domain(self) -> str:
        return self.guess
