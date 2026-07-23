"""
Based on the More Or Less game. A reference person and their asset count are shown. A second
candidate is shown without their count - the player guesses whether it has "more" or "less"
assets than the reference. A correct guess chains into a new round (the candidate becomes the new
reference); a wrong guess ends the game. See docs/GAMES/MORE_OR_LESS.md.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from domain.person import Person
from games.base import BaseGame, BaseRound
from games.serialization import DictCodec
from services.immich_service import ImmichService

Guess = Literal["more", "less"]

GAME_TYPE = "more-or-less"
MODE_PERSON_ASSETS = "personAssets"

# How many random candidates to sample when looking for one whose asset count doesn't tie the
# reference's. Not required for correctness (a tie always counts as a win either way - see
# MoreOrLessRound.calculate_score) - just to keep most rounds a real more/less choice instead of a
# free pass.
_CANDIDATE_SAMPLE_SIZE = 10

# How many of the most-recently-shown people to avoid repeating immediately. The game is infinite
# (it doesn't end just because the library's been fully cycled through) - once a person ages out
# of this window, they're fair game again.
_RECENT_EXCLUDE_WINDOW = 10


@dataclass(frozen=True)
class PersonSnapshot(DictCodec):
    """A person's name/asset count frozen at the moment a round was created - not a live query
    result, so a round's answer stays stable even if the underlying Immich data changes later."""

    id: UUID
    name: str
    asset_count: int

    @classmethod
    def of(cls, person: Person) -> "PersonSnapshot":
        return cls(id=person.id, name=person.name, asset_count=person.asset_count)


def _pick_non_tied_candidate(
    immich_service: ImmichService, reference_asset_count: int, exclude_ids: frozenset[UUID]
) -> Person | None:
    candidates = immich_service.get_persons(
        named_only=True, randomize=True, limit=_CANDIDATE_SAMPLE_SIZE, exclude_ids=exclude_ids
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

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        # No admin-configurable knob affects this game (ADMIN-FEATURE.md point #4) - settings is
        # accepted only to satisfy BaseRound's shared signature.
        if self.candidate.asset_count == self.reference.asset_count:
            # A tie isn't a fair "wrong" either way - always counts as a win.
            return 1
        actual: Guess = "more" if self.candidate.asset_count > self.reference.asset_count else "less"
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
        settings: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            owner=owner,
            game_type=GAME_TYPE,
            mode=MODE_PERSON_ASSETS,
            rounds=rounds,
            score=score,
            finished=finished,
            settings=settings,
        )
        self._immich_service = immich_service

    @classmethod
    def start(
        cls, id: UUID, owner: str, immich_service: ImmichService, settings: Mapping[str, float] | None = None
    ) -> "MoreOrLessGame":
        references = immich_service.get_persons(named_only=True, randomize=True, limit=1)
        if not references:
            raise ValueError("not enough named people in Immich to start a MoreOrLess game")
        [reference] = references
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
        return cls(id=id, owner=owner, rounds=[first_round], immich_service=immich_service, settings=settings)

    def _recent_shown_ids(self) -> frozenset[UUID]:
        """The most-recently-shown people (deduplicated, capped at _RECENT_EXCLUDE_WINDOW) - see
        that constant's docstring. Walks rounds newest-first so "most recent" is accurate."""
        recent: list[UUID] = []
        for round_ in reversed(self.rounds):
            for entity_id in reversed(round_.shown_entities):
                if entity_id not in recent:
                    recent.append(entity_id)
                if len(recent) >= _RECENT_EXCLUDE_WINDOW:
                    return frozenset(recent)
        return frozenset(recent)

    def has_next_round(self) -> bool:
        if self.current_round.score_delta != 1:
            return False
        # Cheap existence check - create_next_round()'s tie-aware pick always succeeds as long as
        # the candidate pool isn't empty (see _pick_non_tied_candidate's fallback), so this is
        # consistent with it without needing to sample _CANDIDATE_SAMPLE_SIZE rows twice.
        remaining = self._immich_service.get_persons(named_only=True, limit=1, exclude_ids=self._recent_shown_ids())
        return bool(remaining)

    def create_next_round(self) -> MoreOrLessRound:
        previous = self.current_round
        candidate = _pick_non_tied_candidate(
            self._immich_service, previous.candidate.asset_count, exclude_ids=self._recent_shown_ids()
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
