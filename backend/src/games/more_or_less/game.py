"""
Based on the More Or Less game. A reference entity and its value are shown. A second candidate is
shown without its value - the player guesses whether it has "more" or "less" than the reference. A
correct guess chains into a new round (the candidate becomes the new reference); a wrong guess ends
the game. See docs/GAMES/MORE_OR_LESS.md.

The game engine here is entity-agnostic: a round compares two "countable entities" (id, name, a
comparable `value`), and everything - chaining, streak scoring, tie handling, the recent-repeat
window, the payload - is independent of *what* the entity is (see games/more_or_less/round.py).
The only thing that varies between modes is where those entities come from, encapsulated in a
`CandidateProvider` (games/more_or_less/content.py) - personAssets -> people, in person_assets.py;
albumAssets -> albums, in album_assets.py.
"""

from collections.abc import Mapping
from uuid import UUID, uuid4

from games.base import BaseGame
from games.more_or_less.content import CandidateProvider, _pick_non_tied_candidate
from games.more_or_less.round import MoreOrLessRound

GAME_TYPE = "more-or-less"
MODE_PERSON_ASSETS = "personAssets"
MODE_ALBUM_ASSETS = "albumAssets"

# How many of the most-recently-shown entities to avoid repeating immediately. The game is infinite
# (it never ends by running out of candidates - see create_next_round's fallback) - once an entity
# ages out of this window, it's fair game again. With a library smaller than this window every
# entity is always "recent", so the fallback is what keeps such a game going.
_RECENT_EXCLUDE_WINDOW = 10


class MoreOrLessGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        mode: str,
        rounds: list[MoreOrLessRound],
        provider: CandidateProvider,
        score: int = 0,
        finished: bool = False,
        settings: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
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
        return cls(id=id, mode=mode, rounds=[first_round], provider=provider, settings=settings)

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
