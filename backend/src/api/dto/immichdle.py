"""Immichdle's request/response DTOs - see api/dto/__init__.py."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import ImmichdleRound


class ImmichdleCluesOut(BaseModel):
    age: Literal["older", "younger", "same", "unknown"]
    asset_count: Literal["more", "less", "equal"]
    first_appearance: Literal["before", "after", "same", "unknown"]
    common_names: int
    ml_similarity: float | None
    assets_together: int
    age_close: bool | None
    first_appearance_close: bool | None
    asset_count_close: bool | None
    age_both_unknown: bool
    first_appearance_both_unknown: bool


class ImmichdleRoundOut(BaseModel):
    game_type: Literal["immichdle"] = IMMICHDLE_TYPE
    id: UUID
    round_index: int
    # Redacted (null) until this round has been answered - same rationale as
    # MoreOrLessRoundOut.candidate_asset_count. The target itself is never in a round's output at
    # all - see GameOut.target_person_id/name.
    guess_person_id: UUID | None
    guess_person_name: str | None
    guess_asset_count: int | None
    guess_birth_date: date | None
    guess_first_asset_date: date | None
    correct: bool | None
    clues: ImmichdleCluesOut | None

    @classmethod
    def from_round(cls, round_: ImmichdleRound) -> "ImmichdleRoundOut":
        answered = round_.answered
        guessed = round_.guessed_person if answered else None
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            guess_person_id=guessed.id if guessed else None,
            guess_person_name=guessed.name if guessed else None,
            guess_asset_count=guessed.asset_count if guessed else None,
            guess_birth_date=guessed.birth_date if guessed else None,
            guess_first_asset_date=guessed.first_asset_date if guessed else None,
            correct=round_.correct,
            clues=ImmichdleCluesOut(**round_.clues.to_dict()) if round_.clues else None,
        )


class ImmichdlePlayRoundIn(BaseModel):
    person_id: UUID

    def to_domain(self) -> UUID:
        return self.person_id
