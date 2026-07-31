"""MoreOrLessRound - a single reference-vs-candidate round and its frozen entity snapshots. See
games/more_or_less/game.py for the loop that drives rounds and games/more_or_less/content.py for
where a round's entities come from."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from games.base import BaseRound
from games.shared.serialization import DictCodec

Guess = Literal["more", "less"]


@dataclass(frozen=True)
class EntitySnapshot(DictCodec):
    """An entity's name/value frozen at the moment a round was created - not a live query result, so
    a round's answer stays stable even if the underlying Immich data changes later. `value` is the
    comparable quantity the round is about (asset count today); it's a JSON scalar so it round-trips
    through the payload as-is and compares with the standard operators."""

    id: UUID
    name: str
    value: int | str


class MoreOrLessRound(BaseRound):
    def __init__(
        self, id: UUID, game_id: UUID, round_index: int, reference: EntitySnapshot, candidate: EntitySnapshot
    ) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[reference.id, candidate.id])
        self.reference = reference
        self.candidate = candidate
        self.guess: Guess | None = None

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        # No admin-configurable knob affects this game (ADMIN-FEATURE.md point #4) - settings is
        # accepted only to satisfy BaseRound's shared signature.
        if self.candidate.value == self.reference.value:
            # A tie isn't a fair "wrong" either way - always counts as a win.
            return 1
        actual: Guess = "more" if self.candidate.value > self.reference.value else "less"
        return 1 if self.guess == actual else 0

    @property
    def correct(self) -> bool | None:
        """Whether the guess was right - None until answered. A win scores 1 (a tie also counts as
        a win, see calculate_score); this is the single definition of "correct" for the DTOs."""
        if not self.answered:
            return None
        return self.score_delta == 1

    def to_payload(self) -> dict[str, Any]:
        return {
            "reference": self.reference.to_dict(),
            "candidate": self.candidate.to_dict(),
            "guess": self.guess,
        }

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "MoreOrLessRound":
        round_ = cls(
            id=id,
            game_id=game_id,
            round_index=round_index,
            reference=EntitySnapshot.from_dict(payload["reference"]),
            candidate=EntitySnapshot.from_dict(payload["candidate"]),
        )
        round_.guess = payload["guess"]
        round_.score_delta = score_delta
        return round_
