"""
Based on the More Or Less game. A reference person and their asset count are shown. A second
candidate is shown without their count - the player guesses whether it has "more" or "less"
assets than the reference. A correct guess chains into a new round (the candidate becomes the new
reference); a wrong guess ends the game. See docs/GAMES/MORE_OR_LESS.md.
"""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from domain.person import Person
from games.base import BaseGame, BaseRound
from services.immich_service import ImmichService

Guess = Literal["more", "less"]

GAME_TYPE = "more-or-less"
MODE_PERSON_ASSETS = "personAssets"

# How many random candidates to sample when looking for one whose asset count doesn't tie the
# reference's - a tie would make the round unanswerable (neither "more" nor "less" would be right).
_CANDIDATE_SAMPLE_SIZE = 10


@dataclass(frozen=True)
class PersonSnapshot:
    """A person's name/asset count frozen at the moment a round was created - not a live query
    result, so a round's answer stays stable even if the underlying Immich data changes later."""

    id: UUID
    name: str
    asset_count: int

    @classmethod
    def of(cls, person: Person) -> "PersonSnapshot":
        return cls(id=person.id, name=person.name, asset_count=person.asset_count)

    def to_dict(self) -> dict[str, Any]:
        return {"id": str(self.id), "name": self.name, "asset_count": self.asset_count}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonSnapshot":
        return cls(id=UUID(data["id"]), name=data["name"], asset_count=data["asset_count"])


def _pick_non_tied_candidate(
    immich_service: ImmichService, reference_asset_count: int, exclude_ids: frozenset[UUID]
) -> Person | None:
    candidates = immich_service.get_persons(
        named_only=True, random=True, limit=_CANDIDATE_SAMPLE_SIZE, exclude_ids=exclude_ids
    )
    if not candidates:
        return None
    for candidate in candidates:
        if candidate.asset_count != reference_asset_count:
            return candidate
    return candidates[0]


class MoreOrLessRound(BaseRound):
    def __init__(
        self, id: UUID, game_id: UUID, round_index: int, reference: PersonSnapshot, candidate: PersonSnapshot
    ) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[reference.id, candidate.id])
        self.reference = reference
        self.candidate = candidate
        self.guess: Guess | None = None

    def calculate_score(self) -> int:
        actual: Guess = "more" if self.candidate.asset_count > self.reference.asset_count else "less"
        return 1 if self.guess == actual else 0

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
            reference=PersonSnapshot.from_dict(payload["reference"]),
            candidate=PersonSnapshot.from_dict(payload["candidate"]),
        )
        round_.guess = payload["guess"]
        round_.score_delta = score_delta
        return round_


class MoreOrLessGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        owner: str,
        rounds: list[MoreOrLessRound],
        immich_service: ImmichService,
        score: int = 0,
        finished: bool = False,
    ) -> None:
        super().__init__(
            id=id,
            owner=owner,
            game_type=GAME_TYPE,
            mode=MODE_PERSON_ASSETS,
            rounds=rounds,
            score=score,
            finished=finished,
        )
        self._immich_service = immich_service

    @classmethod
    def start(cls, id: UUID, owner: str, immich_service: ImmichService) -> "MoreOrLessGame":
        [reference] = immich_service.get_persons(named_only=True, random=True, limit=1)
        candidate = _pick_non_tied_candidate(immich_service, reference.asset_count, exclude_ids=frozenset({reference.id}))
        if candidate is None:
            raise ValueError("not enough named people in Immich to start a MoreOrLess game")

        first_round = MoreOrLessRound(
            id=uuid4(),
            game_id=id,
            round_index=1,
            reference=PersonSnapshot.of(reference),
            candidate=PersonSnapshot.of(candidate),
        )
        return cls(id=id, owner=owner, rounds=[first_round], immich_service=immich_service)

    def _shown_ids(self) -> frozenset[UUID]:
        return frozenset(entity_id for round_ in self.rounds for entity_id in round_.shown_entities)

    def has_next_round(self) -> bool:
        if self.current_round.score_delta != 1:
            return False
        # Cheap existence check - create_next_round()'s tie-aware pick always succeeds as long as
        # the candidate pool isn't empty (see _pick_non_tied_candidate's fallback), so this is
        # consistent with it without needing to sample _CANDIDATE_SAMPLE_SIZE rows twice.
        remaining = self._immich_service.get_persons(named_only=True, limit=1, exclude_ids=self._shown_ids())
        return bool(remaining)

    def create_next_round(self) -> MoreOrLessRound:
        previous = self.current_round
        candidate = _pick_non_tied_candidate(
            self._immich_service, previous.candidate.asset_count, exclude_ids=self._shown_ids()
        )
        if candidate is None:
            raise ValueError("no more candidates left - has_next_round() should have returned False")

        return MoreOrLessRound(
            id=uuid4(),
            game_id=self.id,
            round_index=previous.round_index + 1,
            reference=previous.candidate,
            candidate=PersonSnapshot.of(candidate),
        )
