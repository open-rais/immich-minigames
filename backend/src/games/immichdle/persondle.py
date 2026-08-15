"""
Persondle - Immichdle's original mode. A person is secretly chosen as the target. The player
guesses other named people (by id) - each guess reveals comparative clues about how it relates to
the target: Age, AssetCount, FirstAppearance, CommonNames, MLSimilarity, AssetsTogether. Starting
score is 100, -5 per wrong guess (floored at 0, see games/immichdle/game.py's shared
STARTING_SCORE/WRONG_GUESS_PENALTY). The game ends when a guess is correct (won) or the score hits
0 (lost). See docs/GAMES/IMMICHDLE.md.

Unlike MoreOrLess/Geoguessr/Dateguessr, the guessed entity isn't picked by the server ahead of
time - it's whichever person_id the player submits - so PersondleGame implements
BaseImmichdleGame's `_resolve_and_score_guess` hook to resolve/validate the guess and compute its
clues before scoring.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID, uuid4

from domain.person import Person
from games.immichdle.game import (
    MODE_PERSON,
    STARTING_SCORE,
    BaseImmichdleGame,
    BaseImmichdleRound,
    InvalidGuessError,
    is_close,
)
from games.shared.serialization import DictCodec
from perf import timed
from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService

# Exponent `w` in `peso = c_fotos ^ w` (services/immich/persons.py's get_persons
# asset_count_weight), applied only to the target person's selection at game start
# (PersondleGame.start). w=0 makes every named person equally likely regardless of photo count;
# w=1 makes a person with 1000 photos 1000x as likely as one with 1. Default is a mild bias towards
# people with more photos (0.2), not a strong one.
ASSET_COUNT_WEIGHT_EXPONENT = 0.2

AgeComparison = Literal["older", "younger", "same", "unknown"]
CountComparison = Literal["more", "less", "equal"]
DateComparison = Literal["before", "after", "same", "unknown"]


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
class PersonClues(DictCodec):
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


def _compute_person_clues(
    target: PersonSnapshot, guess: PersonSnapshot, ml_similarity: float | None, assets_together: int
) -> PersonClues:
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

    return PersonClues(
        age=age,
        asset_count=asset_count,
        first_appearance=first_appearance,
        common_names=common_names,
        ml_similarity=ml_similarity,
        assets_together=assets_together,
        age_close=is_close(target.birth_date, guess.birth_date) if age in ("older", "younger") else None,
        first_appearance_close=(
            is_close(target.first_asset_date, guess.first_asset_date)
            if first_appearance in ("before", "after")
            else None
        ),
        asset_count_close=asset_count_close,
        age_both_unknown=target.birth_date is None and guess.birth_date is None,
        first_appearance_both_unknown=target.first_asset_date is None and guess.first_asset_date is None,
    )


class PersondleRound(BaseImmichdleRound):
    def __init__(self, id: UUID, game_id: UUID, round_index: int, target: PersonSnapshot) -> None:
        super().__init__(id, game_id, round_index, target)
        # Both set by apply_guess() before calculate_score() runs - calculate_score() itself stays
        # a trivial, self-contained comparison (matches BaseRound's contract) rather than doing the
        # Immich lookups itself, since only the owning game holds service refs.
        self.guessed_person: PersonSnapshot | None = None
        self.clues: PersonClues | None = None

    @property
    def guessed_entity_id(self) -> UUID | None:
        return self.guessed_person.id if self.guessed_person else None

    def apply_guess(self, guessed: PersonSnapshot, clues: PersonClues) -> None:
        self.guessed_person = guessed
        self.clues = clues
        self.shown_entities = [guessed.id]

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
    ) -> "PersondleRound":
        round_ = cls(
            id=id, game_id=game_id, round_index=round_index, target=PersonSnapshot.from_dict(payload["target"])
        )
        round_.guess = UUID(payload["guess"]) if payload["guess"] else None
        round_.guessed_person = (
            PersonSnapshot.from_dict(payload["guessed_person"]) if payload["guessed_person"] else None
        )
        round_.clues = PersonClues.from_dict(payload["clues"]) if payload["clues"] else None
        round_.score_delta = score_delta
        if round_.guessed_person is not None:
            round_.shown_entities = [round_.guessed_person.id]
        return round_


class PersondleGame(BaseImmichdleGame):
    def __init__(
        self,
        id: UUID,
        rounds: list[PersondleRound],
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        score: int = STARTING_SCORE,
        finished: bool = False,
        settings: dict[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            mode=MODE_PERSON,
            rounds=rounds,
            immich_service=immich_service,
            ml_service=ml_service,
            score=score,
            finished=finished,
            settings=settings,
        )

    @classmethod
    def start(
        cls,
        id: UUID,
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        settings: dict[str, float] | None = None,
        target: PersonSnapshot | None = None,
    ) -> "PersondleGame":
        # A daily game hands in its pre-generated target (games/immichdle/persondle.py's
        # build_spec below) instead of sampling one here; guesses stay live either way
        # (_resolve_and_score_guess always queries immich_service for whatever the player types),
        # so nothing downstream of this needs to know whether the target came from a live sample or
        # a frozen spec.
        if target is None:
            asset_count_weight = float((settings or {}).get("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT))
            if (settings or {}).get("require_birth_date", 0):
                # The requirement is "the target has a birth date", not "two people with a birth
                # date exist" - the alternative-exists check below stays unfiltered (any named
                # person makes the target non-trivially guessable), so this can't reuse the single
                # fused query below. Two queries instead of one, only when the setting is active.
                target_people = immich_service.get_persons(
                    named_only=True,
                    with_birthdate=True,
                    randomize=True,
                    limit=1,
                    asset_count_weight=asset_count_weight,
                )
                if not target_people:
                    raise ValueError(
                        "no named person with a birth date in Immich to start a Persondle game "
                        "(require_birth_date is enabled)"
                    )
                if len(immich_service.get_persons(named_only=True, limit=2)) < 2:
                    raise ValueError("not enough named people in Immich to start a Persondle game")
                target_person = target_people[0]
            else:
                # limit=2 in one call instead of a second get_persons just to check an alternative
                # exists - that second query repeated the full asset_face aggregation for nothing
                # more than an existence check.
                target_people = immich_service.get_persons(
                    named_only=True, randomize=True, limit=2, asset_count_weight=asset_count_weight
                )
                if len(target_people) < 2:
                    raise ValueError("not enough named people in Immich to start a Persondle game")
                target_person = target_people[0]

            target = PersonSnapshot.of(
                target_person, first_asset_date=immich_service.get_person_first_asset_date(target_person.id)
            )

        first_round = PersondleRound(id=uuid4(), game_id=id, round_index=1, target=target)
        starting_score = int((settings or {}).get("starting_score", STARTING_SCORE))
        return cls(
            id=id,
            rounds=[first_round],
            immich_service=immich_service,
            ml_service=ml_service,
            score=starting_score,
            settings=settings,
        )

    def _resolve_and_score_guess(self, guess: UUID) -> tuple[PersonSnapshot, PersonClues]:
        # Four queries timed individually at DEBUG to find out which one actually dominates a
        # big-person guess (roadmap #15's homelab-crash diagnosis).
        with timed("persondle.get_persons", person_id=str(guess)):
            matches = self._immich_service.get_persons(named_only=True, ids=frozenset({guess}), limit=1)
        if not matches:
            raise InvalidGuessError(f"person {guess} is not a valid named person to guess")
        guessed_person = matches[0]
        with timed("persondle.get_person_first_asset_date", person_id=str(guessed_person.id)):
            first_asset_date = self._immich_service.get_person_first_asset_date(guessed_person.id)
        guessed = PersonSnapshot.of(guessed_person, first_asset_date=first_asset_date)
        with timed("persondle.face_similarity", target_id=str(self.target.id), guess_id=str(guessed.id)):
            ml_similarity = self._ml_service.face_similarity(self.target.id, guessed.id)
        with timed("persondle.get_assets_together_count", target_id=str(self.target.id), guess_id=str(guessed.id)):
            assets_together = self._immich_service.get_assets_together_count(self.target.id, guessed.id)
        clues = _compute_person_clues(
            target=self.target,
            guess=guessed,
            ml_similarity=ml_similarity,
            assets_together=assets_together,
        )
        return guessed, clues

    def create_next_round(self) -> PersondleRound:
        previous = self.current_round
        return PersondleRound(id=uuid4(), game_id=self.id, round_index=previous.round_index + 1, target=self.target)


def build_spec(immich_service: ContentQueries, settings: dict[str, float]) -> dict[str, Any]:
    # Replicates PersondleGame.start()'s target-selection directly rather than driving a full game
    # instance, since there's no round sequence to precompute.
    weight = float(settings.get("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT))
    require_birth_date = bool(settings.get("require_birth_date", 0))
    targets = immich_service.get_persons(
        named_only=True,
        with_birthdate=True if require_birth_date else None,
        randomize=True,
        limit=1,
        asset_count_weight=weight,
    )
    if not targets:
        message = (
            "no named person with a birth date in Immich to generate a daily Persondle challenge "
            "(require_birth_date is enabled)"
            if require_birth_date
            else "not enough named people in Immich to generate a daily Persondle challenge"
        )
        raise ValueError(message)
    [target_person] = targets
    # Mirrors PersondleGame.start()'s has_alternative check - with exactly one named person the
    # normal game refuses to start (the target would be trivially guessable), so the daily must
    # too. Phrased as "at least two named people exist" - equivalent to "someone besides the
    # (named) target exists". When a no-repeat-window wrapper widens this query's exclusions the
    # check can come out stricter than the real game's, but a failure then just triggers
    # get_or_create_challenge's no-exclusion retry, where it's exact.
    if len(immich_service.get_persons(named_only=True, limit=2)) < 2:
        raise ValueError("not enough named people in Immich to generate a daily Persondle challenge")
    target = PersonSnapshot.of(
        target_person, first_asset_date=immich_service.get_person_first_asset_date(target_person.id)
    )
    return {"target": target.to_dict()}


def game_kwargs(
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"immich_service": immich_service, "ml_service": ml_service, "settings": settings}
    # Only the very first round needs the target explicitly - PersondleRound.from_payload already
    # carries it for every later reconstruction (see games/immichdle/game.py's
    # BaseImmichdleGame.target).
    if rounds_played == 0:
        kwargs["target"] = PersonSnapshot.from_dict(spec["target"])
    return kwargs
