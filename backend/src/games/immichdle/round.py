"""ImmichdleRound - a single guess-the-person round, its frozen target/guess snapshots, and the
wrong-guess-penalty scoring. See games/immichdle/game.py for the loop that drives rounds (including
guess resolution) and games/immichdle/clues.py for the comparison logic that fills in `clues`."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from domain.person import Person
from games.base import BaseRound
from games.shared.serialization import DictCodec

if TYPE_CHECKING:
    from games.immichdle.clues import ImmichdleClues

WRONG_GUESS_PENALTY = 5


@dataclass(frozen=True)
class PersonSnapshot(DictCodec):
    """A person's identifying data frozen at the moment it's looked up (target at game start,
    guess at guess time) - not a live query result, so a round's revealed data stays stable even
    if the underlying Immich data changes later (same rationale as more_or_less.py's
    PersonSnapshot)."""

    id: UUID
    name: str
    asset_count: int
    birth_date: date | None
    first_asset_date: date | None

    @classmethod
    def of(cls, person: Person, first_asset_date: date | None) -> "PersonSnapshot":
        return cls(
            id=person.id,
            name=person.name,
            asset_count=person.asset_count,
            birth_date=person.birth_date,
            first_asset_date=first_asset_date,
        )


class ImmichdleRound(BaseRound):
    def __init__(self, id: UUID, game_id: UUID, round_index: int, target: PersonSnapshot) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[])
        self.target = target
        self.guess: UUID | None = None
        # Both set by ImmichdleGame.play_round() before calculate_score() runs - calculate_score()
        # itself stays a trivial, self-contained comparison (matches BaseRound's contract) rather
        # than doing the Immich lookups itself, since only the owning game holds service refs.
        self.guessed_person: PersonSnapshot | None = None
        self.clues: "ImmichdleClues | None" = None  # noqa: UP037 (ImmichdleClues is TYPE_CHECKING-only - unquoting NameErrors at runtime)

    @property
    def correct(self) -> bool | None:
        """Whether the guess was the target - None until answered. Single definition of "correct"
        for the DTOs, same role as MoreOrLessRound.correct."""
        if not self.answered:
            return None
        if self.guessed_person is None:
            raise RuntimeError("correct accessed on an answered round with no guessed_person set")
        return self.guessed_person.id == self.target.id

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        if self.guessed_person is None:
            raise RuntimeError("calculate_score() called before ImmichdleGame.play_round set guessed_person")
        penalty = (settings or {}).get("wrong_guess_penalty", WRONG_GUESS_PENALTY)
        return 0 if self.correct else -int(penalty)

    def to_payload(self) -> dict[str, Any]:
        return {
            "target": self.target.to_dict(),
            "guess": str(self.guess) if self.guess else None,
            "guessed_person": self.guessed_person.to_dict() if self.guessed_person else None,
            "clues": self.clues.to_dict() if self.clues else None,
        }

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "ImmichdleRound":
        from games.immichdle.clues import ImmichdleClues

        round_ = cls(
            id=id, game_id=game_id, round_index=round_index, target=PersonSnapshot.from_dict(payload["target"])
        )
        round_.guess = UUID(payload["guess"]) if payload["guess"] else None
        round_.guessed_person = (
            PersonSnapshot.from_dict(payload["guessed_person"]) if payload["guessed_person"] else None
        )
        round_.clues = ImmichdleClues.from_dict(payload["clues"]) if payload["clues"] else None
        round_.score_delta = score_delta
        if round_.guessed_person is not None:
            round_.shown_entities = [round_.guessed_person.id]
        return round_
