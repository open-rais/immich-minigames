"""
Based on the *dle games (Wordle). Shared engine both Immichdle modes plug into - persondle.py
(guess the mystery person) and albumdle.py (guess the mystery album, roadmap #14). Unlike
MoreOrLess's modes (which share one fully generic MoreOrLessGame/MoreOrLessRound because every
mode compares one generic `value`), persondle's and albumdle's clue systems are NOT generically
shareable - albumdle's dominant-face clue has no persondle equivalent at all - so only what's
genuinely identical lives here: the duplicate-guess/finished checks, the play_round loop shape,
has_next_round, and the correct/calculate_score round mechanics. Each mode still owns its own
concrete Round/Game classes, its own snapshot/clue types, and its own create_next_round (see
games/base.py's BaseGame for why that one isn't hoisted here either - it's the same 4-line shape
in both modes, but naming a different concrete Round class, so sharing it would trade away
type-checker clarity for no real behavior in common).

Starting score is 100, -5 per wrong guess (floored at 0) for both modes - see
games/immichdle/persondle.py / albumdle.py for each mode's own docstring and scoring/termination
specifics.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import date
from typing import Any
from uuid import UUID

from games.base import BaseGame, BaseRound, PlayRoundResult
from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService

GAME_TYPE = "immichdle"
MODE_PERSON = "person"
MODE_ALBUM = "album"


def extra_kwargs(content_source: ContentQueries, ml_service: MLService, mode: str) -> dict[str, Any]:
    """games/registry.py's GameSpec.extra_kwargs for both Immichdle modes - PersondleGame and
    AlbumdleGame both need ml_service (face/album similarity clues) on top of the immich_service
    GameFactory.kwargs_for already assembles for them (neither sets a provider_factory/
    content_factory)."""
    return {"ml_service": ml_service}

# Admin feature - public (no leading underscore) since services/game_settings_service.py assembles
# these as defaults for the admin-configurable starting_score/wrong_guess_penalty settings, same
# convention already used by e.g. games/geoguessr/game.py's TOTAL_ROUNDS/MAX_SCORE. Shared by both
# modes (see settings.py's SETTING_SPECS, one entry per mode using these same defaults).
STARTING_SCORE = 100
WRONG_GUESS_PENALTY = 5


class DuplicateGuessError(Exception):
    pass


class InvalidGuessError(Exception):
    pass


def is_close(target_date: date | None, guess_date: date | None) -> bool | None:
    """Whether two dates are within a year of each other - None if either is unknown. Shared by
    both modes' clue computation (persondle's age/first_appearance, albumdle's
    first_asset_date) - same magnitude-bucket-not-raw-diff rationale each mode's own clues
    dataclass documents."""
    if target_date is None or guess_date is None:
        return None
    return abs((guess_date - target_date).days) < 365


class BaseImmichdleRound(BaseRound, ABC):
    """Shared round shape: a frozen `target` snapshot, the mode's own `clues` result (typed `Any`
    here - persondle.py/albumdle.py narrow it), and the guess-correctness/scoring mechanics that
    don't depend on which entity type is being guessed. Concrete subclasses add their own
    `guessed_person`/`guessed_album` attribute (there isn't one generic name worth forcing both
    modes to share) via `apply_guess`, and expose its id via `guessed_entity_id` - the one thing
    `correct` needs without knowing that attribute's name."""

    def __init__(self, id: UUID, game_id: UUID, round_index: int, target: Any) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[])
        self.target = target
        self.guess: UUID | None = None
        self.clues: Any | None = None

    @property
    @abstractmethod
    def guessed_entity_id(self) -> UUID | None:
        """The resolved guess's id (persondle: guessed_person.id, albumdle: guessed_album.id) -
        None until answered."""

    @abstractmethod
    def apply_guess(self, guessed: Any, clues: Any) -> None:
        """Sets this round's mode-specific guessed-entity attribute, `clues`, and
        `shown_entities` - called by BaseImmichdleGame.play_round once the guess has been resolved
        and scored."""

    @property
    def correct(self) -> bool | None:
        """Whether the guess was the target - None until answered. Single definition of "correct"
        for the DTOs, same role as MoreOrLessRound.correct."""
        if not self.answered:
            return None
        entity_id = self.guessed_entity_id
        if entity_id is None:
            raise RuntimeError("correct accessed on an answered round with no guessed entity set")
        return entity_id == self.target.id

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        if self.guessed_entity_id is None:
            raise RuntimeError("calculate_score() called before apply_guess() set the guessed entity")
        penalty = (settings or {}).get("wrong_guess_penalty", WRONG_GUESS_PENALTY)
        return 0 if self.correct else -int(penalty)


class BaseImmichdleGame(BaseGame, ABC):
    """Shared game shape: both modes pick a target once (frozen on the first round), let the
    player guess entities by id, and score/end the same way (see calculate_score/has_next_round
    below) - only *how* a guess is resolved into a snapshot+clues differs, via the abstract
    `_resolve_and_score_guess` hook."""

    def __init__(
        self,
        id: UUID,
        mode: str,
        rounds: list[BaseImmichdleRound],
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        score: int = STARTING_SCORE,
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
        self._immich_service = immich_service
        # Injected by GameFactory - defaults to self-constructing when omitted (tests, a one-off
        # script), same pattern ImmichService() itself uses elsewhere.
        self._ml_service = ml_service or MLService()

    @property
    def target(self) -> Any:
        # The target is the same for every round of the game (unlike MoreOrLess's chaining
        # reference/candidate) - stored once, on the first round's payload, since GameModel has no
        # game-level payload column of its own (see persistence/games.py).
        return self.rounds[0].target

    def _guessed_ids(self) -> frozenset[UUID]:
        return frozenset(round_.guess for round_ in self.rounds if round_.guess is not None)

    @abstractmethod
    def _resolve_and_score_guess(self, guess: UUID) -> tuple[Any, Any]:
        """Looks up `guess` as this mode's entity (raises InvalidGuessError if it isn't a valid
        one to guess) and computes its clues against self.target - called before any round state
        is mutated, matching persondle's original ordering (validate, then mutate). Returns
        (guessed_snapshot, clues)."""

    def play_round(self, guess: UUID) -> PlayRoundResult:
        if self.finished:
            raise ValueError("game is already finished")
        if guess in self._guessed_ids():
            raise DuplicateGuessError(f"{self.mode} entity {guess} was already guessed in this game")

        guessed, clues = self._resolve_and_score_guess(guess)

        current = self.current_round
        current.guess = guess
        current.apply_guess(guessed, clues)
        current.score_delta = current.calculate_score(self._settings)
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
