"""
Based on the More Or Less game. A reference entity and its value are shown. A second candidate is
shown without its value - the player guesses whether it has "more" or "less" than the reference. A
correct guess chains into a new round (the candidate becomes the new reference); a wrong guess ends
the game. See docs/GAMES/MORE_OR_LESS.md.

The game engine here is entity-agnostic: a round compares two "countable entities" (id, name, a
comparable `value`), and everything - chaining, streak scoring, tie handling, the recent-repeat
window, the payload - is independent of *what* the entity is. The only thing that varies between
modes is where those entities come from, encapsulated in a `CandidateProvider` (personAssets ->
people, albumAssets -> albums). `value` is a comparable JSON scalar (int for the asset-count modes
today; an ISO date string would slot in for a future date-comparing mode - ISO dates compare
chronologically as strings - without changing this engine).
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from games.base import BaseGame, BaseRound
from games.serialization import DictCodec
from services.immich_service import ImmichService

Guess = Literal["more", "less"]

GAME_TYPE = "more-or-less"
MODE_PERSON_ASSETS = "personAssets"
MODE_ALBUM_ASSETS = "albumAssets"

# How many random candidates to sample when looking for one whose value doesn't tie the
# reference's. Not required for correctness (a tie always counts as a win either way - see
# MoreOrLessRound.calculate_score) - just to keep most rounds a real more/less choice instead of a
# free pass.
_CANDIDATE_SAMPLE_SIZE = 10

# How many of the most-recently-shown entities to avoid repeating immediately. The game is infinite
# (it never ends by running out of candidates - see create_next_round's fallback) - once an entity
# ages out of this window, it's fair game again. With a library smaller than this window every
# entity is always "recent", so the fallback is what keeps such a game going.
_RECENT_EXCLUDE_WINDOW = 10


@dataclass(frozen=True)
class EntitySnapshot(DictCodec):
    """An entity's name/value frozen at the moment a round was created - not a live query result, so
    a round's answer stays stable even if the underlying Immich data changes later. `value` is the
    comparable quantity the round is about (asset count today); it's a JSON scalar so it round-trips
    through the payload as-is and compares with the standard operators."""

    id: UUID
    name: str
    value: int | str


class CandidateProvider(ABC):
    """Supplies the entities a MoreOrLess mode compares. This is the single point of variation
    between modes: personAssets samples named people, albumAssets samples albums, a future
    date-based mode would sample something else - the game engine below never knows which."""

    @abstractmethod
    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        """A random sample of up to `limit` entities (id, name, comparable value), excluding
        `exclude_ids`. May return fewer than `limit` (or none) when the pool is that small."""

    @abstractmethod
    def any_exist(self) -> bool:
        """Whether the pool has at least one entity at all - guards against an empty library. The
        game never ends merely because the *recently shown* ones are excluded (see
        create_next_round's fallback), so this ignores any recent-window exclusion."""


class PersonAssetsProvider(CandidateProvider):
    def __init__(self, immich_service: ImmichService) -> None:
        self._immich_service = immich_service

    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        people = self._immich_service.get_persons(
            named_only=True, randomize=True, limit=limit, exclude_ids=exclude_ids
        )
        return [EntitySnapshot(id=p.id, name=p.name, value=p.asset_count) for p in people]

    def any_exist(self) -> bool:
        return bool(self._immich_service.get_persons(named_only=True, limit=1))


class AlbumAssetsProvider(CandidateProvider):
    def __init__(self, immich_service: ImmichService) -> None:
        self._immich_service = immich_service

    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        albums = self._immich_service.get_albums(randomize=True, limit=limit, exclude_ids=exclude_ids)
        return [EntitySnapshot(id=a.id, name=a.name, value=a.asset_count) for a in albums]

    def any_exist(self) -> bool:
        return bool(self._immich_service.get_albums(limit=1))


def _pick_non_tied_candidate(
    provider: CandidateProvider, reference_value: int | str, exclude_ids: frozenset[UUID]
) -> EntitySnapshot | None:
    candidates = provider.sample(limit=_CANDIDATE_SAMPLE_SIZE, exclude_ids=exclude_ids)
    if not candidates:
        return None
    for candidate in candidates:
        if candidate.value != reference_value:
            return candidate
    return candidates[0]


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


class MoreOrLessGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        owner: str,
        mode: str,
        rounds: list[MoreOrLessRound],
        provider: CandidateProvider,
        score: int = 0,
        finished: bool = False,
        settings: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            owner=owner,
            game_type=GAME_TYPE,
            mode=mode,
            rounds=rounds,
            score=score,
            finished=finished,
            settings=settings,
        )
        self._provider = provider

    @classmethod
    def start(
        cls,
        id: UUID,
        owner: str,
        mode: str,
        provider: CandidateProvider,
        settings: Mapping[str, float] | None = None,
    ) -> "MoreOrLessGame":
        references = provider.sample(limit=1, exclude_ids=frozenset())
        if not references:
            raise ValueError("not enough entities in Immich to start a MoreOrLess game")
        [reference] = references
        candidate = _pick_non_tied_candidate(provider, reference.value, exclude_ids=frozenset({reference.id}))
        if candidate is None:
            raise ValueError("not enough entities in Immich to start a MoreOrLess game")

        first_round = MoreOrLessRound(
            id=uuid4(),
            game_id=id,
            round_index=1,
            reference=reference,
            candidate=candidate,
        )
        return cls(id=id, owner=owner, mode=mode, rounds=[first_round], provider=provider, settings=settings)

    def _recent_shown_ids(self) -> frozenset[UUID]:
        """The most-recently-shown entities (deduplicated, capped at _RECENT_EXCLUDE_WINDOW) - see
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
        # The game is infinite: it continues on any correct/tied guess as long as the pool has at
        # least one entity at all (create_next_round falls back to allowing repeats when the recent
        # window covers the whole pool), and only ends on a wrong guess.
        if self.current_round.score_delta != 1:
            return False
        return self._provider.any_exist()

    def create_next_round(self) -> MoreOrLessRound:
        previous = self.current_round
        candidate = _pick_non_tied_candidate(
            self._provider, previous.candidate.value, exclude_ids=self._recent_shown_ids()
        )
        if candidate is None:
            # The recent-exclude window covers the entire pool (a library smaller than the window) -
            # allow a repeat rather than ending, so the game stays infinite (see docs/GAMES/
            # MORE_OR_LESS.md and _RECENT_EXCLUDE_WINDOW).
            candidate = _pick_non_tied_candidate(self._provider, previous.candidate.value, exclude_ids=frozenset())
        if candidate is None:
            raise ValueError("no candidates left - has_next_round() should have returned False")

        return MoreOrLessRound(
            id=uuid4(),
            game_id=self.id,
            round_index=previous.round_index + 1,
            reference=previous.candidate,
            candidate=candidate,
        )
