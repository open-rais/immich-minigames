"""Timeline's request/response DTOs - see api/dto/__init__.py."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, model_validator

from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline import TimelineRound


class TimelineCardOut(BaseModel):
    asset_id: UUID
    date: date


class TimelineRoundOut(BaseModel):
    game_type: Literal["timeline"] = TIMELINE_TYPE
    id: UUID
    round_index: int
    board: list[TimelineCardOut]
    card_asset_id: UUID
    guess_slot: int | None
    # Redacted (null) until this round has been answered - it IS the answer (docs/TODO/TIMELINE.md
    # decision [H]'s "partida en curso abierta por URL" risk row).
    card_date: date | None
    correct_slot: int | None
    correct: bool | None
    score_delta: int | None

    @classmethod
    def from_round(cls, round_: TimelineRound) -> "TimelineRoundOut":
        answered = round_.answered
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            board=[TimelineCardOut(asset_id=card.id, date=card.date) for card in round_.board],
            card_asset_id=round_.card.id,
            guess_slot=round_.guess,
            card_date=round_.card.date if answered else None,
            correct_slot=round_.correct_slot if answered else None,
            correct=round_.correct,
            score_delta=round_.score_delta,
        )


class TimelinePlayRoundIn(BaseModel):
    slot: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_slot_within_board(self, info: ValidationInfo) -> "TimelinePlayRoundIn":
        # The upper bound (len(board)) is per-round, not a static schema constraint - api/dto/
        # common.py's parse_guess passes the pending round in via model_validate's `context` so this
        # rejects an out-of-range slot here (422), rather than letting it reach the domain layer as
        # a guess that's merely never correct (docs/TODO/TIMELINE.md §4.3).
        round_ = (info.context or {}).get("round") if info.context else None
        if isinstance(round_, TimelineRound) and self.slot > len(round_.board):
            raise ValueError(f"slot must be between 0 and {len(round_.board)}")
        return self

    def to_domain(self) -> int:
        return self.slot
