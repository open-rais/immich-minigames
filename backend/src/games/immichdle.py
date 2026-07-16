"""
Based on the *dle games (Wordle). A person is secretly chosen as the target. The player guesses
other named people (by id) - each guess reveals comparative clues about how it relates to the
target: Age, AssetCount, FirstAppearance, CommonNames, MLSimilarity, AssetsTogether. Starting score
is 100, -5 per wrong guess (floored at 0). The game ends when a guess is correct (won) or the score
hits 0 (lost). See docs/GAMES/IMMICHDLE.md.

Unlike MoreOrLess/Geoguessr/Dateguessr, the guessed entity isn't picked by the server ahead of
time - it's whichever person_id the player submits - so ImmichdleGame overrides play_round() to
resolve/validate the guess and compute its clues before scoring (see calculate_score()'s docstring
for why that split exists).
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID, uuid4

from domain.person import Person
from games.base import BaseGame, BaseRound, PlayRoundResult
from games.serialization import DictCodec
from services.immich_service import ImmichService
from services.ml_service import MLService

GAME_TYPE = "immichdle"
MODE_PERSON = "person"

_STARTING_SCORE = 100
_WRONG_GUESS_PENALTY = 5

AgeComparison = Literal["older", "younger", "same", "unknown"]
CountComparison = Literal["more", "less", "equal"]
DateComparison = Literal["before", "after", "same", "unknown"]


class DuplicateGuessError(Exception):
    pass


class InvalidGuessError(Exception):
    pass


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


@dataclass(frozen=True)
class ImmichdleClues(DictCodec):
    age: AgeComparison
    asset_count: CountComparison
    first_appearance: DateComparison
    common_names: int
    ml_similarity: float | None
    assets_together: int
    # Magnitude buckets, not exact diffs - the target's birth_date/first_asset_date/asset_count stay
    # secret until the game ends, and an exact diff (e.g. "3 days younger") combined with the
    # guessed person's own public date/count would pin down the target's exact value from a single
    # guess, breaking the Wordle-style narrowing. None whenever the underlying comparison has no
    # meaningful magnitude ("same"/"equal"/"unknown").
    age_close: bool | None
    first_appearance_close: bool | None
    asset_count_close: bool | None
    # Only meaningful when age/first_appearance == "unknown" - that single enum value covers both
    # "neither person has a date" and "only the target's is missing" (the guess's own date, when
    # known, is already visible via ImmichdleRoundOut.guess_birth_date/guess_first_asset_date, so
    # only the "guess's date is also missing" case is actually ambiguous without this bit). Revealing
    # this one bit (not the target's date itself) is the same bucket-not-raw-value tradeoff as
    # *_close above.
    age_both_unknown: bool
    first_appearance_both_unknown: bool


def _is_close(target_date: date | None, guess_date: date | None) -> bool | None:
    """Whether two dates are within a year of each other - None if either is unknown."""
    if target_date is None or guess_date is None:
        return None
    return abs((guess_date - target_date).days) < 365


def _compute_clues(
    target: PersonSnapshot, guess: PersonSnapshot, ml_similarity: float | None, assets_together: int
) -> ImmichdleClues:
    """Every comparison is guess-relative-to-target (e.g. "older" means the guess is older than
    the target) - mirrors how more_or_less.py describes its candidate relative to its reference."""
    if target.birth_date is None or guess.birth_date is None:
        age: AgeComparison = "unknown"
    elif guess.birth_date < target.birth_date:
        age = "older"
    elif guess.birth_date > target.birth_date:
        age = "younger"
    else:
        age = "same"

    if guess.asset_count > target.asset_count:
        asset_count: CountComparison = "more"
    elif guess.asset_count < target.asset_count:
        asset_count = "less"
    else:
        asset_count = "equal"

    if target.first_asset_date is None or guess.first_asset_date is None:
        first_appearance: DateComparison = "unknown"
    elif guess.first_asset_date < target.first_asset_date:
        first_appearance = "before"
    elif guess.first_asset_date > target.first_asset_date:
        first_appearance = "after"
    else:
        first_appearance = "same"

    common_names = len(set(target.name.lower().split()) & set(guess.name.lower().split()))

    asset_count_close = None if asset_count == "equal" else abs(guess.asset_count - target.asset_count) < 100

    return ImmichdleClues(
        age=age,
        asset_count=asset_count,
        first_appearance=first_appearance,
        common_names=common_names,
        ml_similarity=ml_similarity,
        assets_together=assets_together,
        age_close=_is_close(target.birth_date, guess.birth_date) if age in ("older", "younger") else None,
        first_appearance_close=(
            _is_close(target.first_asset_date, guess.first_asset_date) if first_appearance in ("before", "after") else None
        ),
        asset_count_close=asset_count_close,
        age_both_unknown=target.birth_date is None and guess.birth_date is None,
        first_appearance_both_unknown=target.first_asset_date is None and guess.first_asset_date is None,
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
        self.clues: ImmichdleClues | None = None

    @property
    def correct(self) -> bool | None:
        """Whether the guess was the target - None until answered. Single definition of "correct"
        for the DTOs, same role as MoreOrLessRound.correct."""
        if not self.answered:
            return None
        assert self.guessed_person is not None
        return self.guessed_person.id == self.target.id

    def calculate_score(self) -> int:
        assert self.guessed_person is not None  # set by ImmichdleGame.play_round before this runs
        return 0 if self.correct else -_WRONG_GUESS_PENALTY

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
        round_ = cls(id=id, game_id=game_id, round_index=round_index, target=PersonSnapshot.from_dict(payload["target"]))
        round_.guess = UUID(payload["guess"]) if payload["guess"] else None
        round_.guessed_person = PersonSnapshot.from_dict(payload["guessed_person"]) if payload["guessed_person"] else None
        round_.clues = ImmichdleClues.from_dict(payload["clues"]) if payload["clues"] else None
        round_.score_delta = score_delta
        if round_.guessed_person is not None:
            round_.shown_entities = [round_.guessed_person.id]
        return round_


class ImmichdleGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        owner: str,
        rounds: list[ImmichdleRound],
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        score: int = _STARTING_SCORE,
        finished: bool = False,
    ) -> None:
        super().__init__(
            id=id,
            owner=owner,
            game_type=GAME_TYPE,
            mode=MODE_PERSON,
            rounds=rounds,
            score=score,
            finished=finished,
        )
        self._immich_service = immich_service
        # Injected by GamesService (see services/games_service.py's _game_kwargs), which is the only
        # game-specific dependency any game currently needs beyond immich_service. Still defaults to
        # self-constructing when omitted - same default-construction pattern ImmichService() itself
        # uses elsewhere (e.g. api/api.py's get_immich_service) - so direct/low-level construction
        # (tests, a one-off script) doesn't have to wire up an MLService just to build a game.
        self._ml_service = ml_service or MLService()

    @property
    def target(self) -> PersonSnapshot:
        # The target is the same for every round of the game (unlike MoreOrLess's chaining
        # reference/candidate) - stored once, on the first round's payload, since GameModel has no
        # game-level payload column of its own (see persistence/games.py).
        return self.rounds[0].target

    @classmethod
    def start(
        cls, id: UUID, owner: str, immich_service: ImmichService, ml_service: MLService | None = None
    ) -> "ImmichdleGame":
        [target_person] = immich_service.get_persons(named_only=True, random=True, limit=1)
        has_alternative = immich_service.get_persons(
            named_only=True, limit=1, exclude_ids=frozenset({target_person.id})
        )
        if not has_alternative:
            raise ValueError("not enough named people in Immich to start an Immichdle game")

        target = PersonSnapshot.of(
            target_person, first_asset_date=immich_service.get_person_first_asset_date(target_person.id)
        )
        first_round = ImmichdleRound(id=uuid4(), game_id=id, round_index=1, target=target)
        return cls(
            id=id,
            owner=owner,
            rounds=[first_round],
            immich_service=immich_service,
            ml_service=ml_service,
            score=_STARTING_SCORE,
        )

    def _guessed_person_ids(self) -> frozenset[UUID]:
        return frozenset(round_.guess for round_ in self.rounds if round_.guess is not None)

    def play_round(self, guess: UUID) -> PlayRoundResult:
        if self.finished:
            raise ValueError("game is already finished")
        if guess in self._guessed_person_ids():
            raise DuplicateGuessError(f"person {guess} was already guessed in this game")

        matches = self._immich_service.get_persons(named_only=True, ids=frozenset({guess}), limit=1)
        if not matches:
            raise InvalidGuessError(f"person {guess} is not a valid named person to guess")
        guessed = matches[0]

        current = self.current_round
        current.guess = guess
        current.guessed_person = PersonSnapshot.of(
            guessed, first_asset_date=self._immich_service.get_person_first_asset_date(guessed.id)
        )
        current.clues = _compute_clues(
            target=current.target,
            guess=current.guessed_person,
            ml_similarity=self._ml_service.face_similarity(current.target.id, guessed.id),
            assets_together=self._immich_service.get_assets_together_count(current.target.id, guessed.id),
        )
        current.shown_entities = [guessed.id]
        current.score_delta = current.calculate_score()
        self.score = max(0, self.score + current.score_delta)

        if self.has_next_round():
            self.rounds.append(self.create_next_round())
        else:
            self.finished = True

        return PlayRoundResult(score_delta=current.score_delta, score=self.score, finished=self.finished)

    def has_next_round(self) -> bool:
        if self.current_round.correct:
            return False
        return self.score > 0

    def create_next_round(self) -> ImmichdleRound:
        previous = self.current_round
        return ImmichdleRound(id=uuid4(), game_id=self.id, round_index=previous.round_index + 1, target=self.target)
