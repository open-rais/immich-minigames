"""Trivium's request/response DTOs - see api/dto/__init__.py."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from games.trivium import GAME_TYPE as TRIVIUM_TYPE
from games.trivium import Answer, MediaKind, TriviumRound


class TriviumMediaOut(BaseModel):
    kind: MediaKind
    asset_id: UUID | None = None
    person_id: UUID | None = None
    person_ids: list[UUID] | None = None


class TriviumRoundOut(BaseModel):
    game_type: Literal["trivium"] = TRIVIUM_TYPE
    id: UUID
    round_index: int
    question_kind: str
    # Render data for the question - e.g. {"person_id": ..., "person_name": ...} for
    # birthday_year. Never a pre-built phrase - the app is translated ES/EN, so the frontend
    # builds the actual sentence from question_kind + these.
    params: dict[str, Any]
    alternatives: list[Any]
    media: TriviumMediaOut
    # Redacted (null) until this round has been answered - otherwise the correct answer could be
    # read straight out of the HTTP response before guessing (same rationale as every other
    # game's *Out DTOs).
    correct_index: int | None
    guess: int | None
    elapsed_ms: int | None
    correct: bool | None

    @classmethod
    def from_round(cls, round_: TriviumRound) -> "TriviumRoundOut":
        guess = round_.guess
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            question_kind=round_.question_kind,
            params=round_.params,
            alternatives=round_.alternatives,
            media=TriviumMediaOut(
                kind=round_.media.kind,
                asset_id=round_.media.asset_id,
                person_id=round_.media.person_id,
                person_ids=round_.media.person_ids,
            ),
            correct_index=round_.correct_index if guess is not None else None,
            guess=guess.alternative if guess is not None else None,
            elapsed_ms=guess.elapsed_ms if guess is not None else None,
            correct=round_.correct,
        )


class TriviumPlayRoundIn(BaseModel):
    # Null on a timeout - the frontend must still POST something when the timer runs out (a hung
    # request would never record the loss), just with no chosen alternative.
    alternative: int | None
    elapsed_ms: int

    def to_domain(self) -> Answer:
        return Answer(alternative=self.alternative, elapsed_ms=self.elapsed_ms)
