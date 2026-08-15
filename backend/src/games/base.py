"""
(ABC) Base classes every minigame implements to plug into the shared game loop - see
docs/GAMES/OVERVIEW.md ("Base compartida: Game y Round"). Pure domain objects, not ORM models -
GamesService (services/games_service.py) is responsible for loading/saving them via
persistence/games.py.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID


class BaseRound(ABC):
    def __init__(self, id: UUID, game_id: UUID, round_index: int, shown_entities: list[UUID]) -> None:
        self.id = id
        self.game_id = game_id
        self.round_index = round_index
        self.shown_entities = shown_entities
        self.guess: Any = None
        self.score_delta: int | None = None

    @property
    def answered(self) -> bool:
        return self.guess is not None

    @abstractmethod
    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        """Score delta to apply to the game's total. Only called once `guess` has been set.
        `settings` is this game's live admin-configurable values (see
        services/game_settings_service.py) - implementations without any configurable score knob
        (MoreOrLess, WhosThatPerson today) just ignore it. Defaults to None/{} so direct
        construction (tests, a one-off script) doesn't have to pass one to get the same behavior."""

    @abstractmethod
    def to_payload(self) -> dict[str, Any]:
        """Serializes this round's game-specific data (shown entities, answer, guess) for the
        `payload` JSONB column in persistence/games.py."""

    @classmethod
    @abstractmethod
    def from_payload(
        cls,
        id: UUID,
        game_id: UUID,
        round_index: int,
        payload: dict[str, Any],
        score_delta: int | None,
    ) -> "BaseRound":
        """Reconstructs a round from its persisted row (payload + the score_delta column)."""


@dataclass
class PlayRoundResult:
    score_delta: int
    score: int
    finished: bool


class BaseGame(ABC):
    def __init__(
        self,
        id: UUID,
        game_type: str,
        mode: str,
        rounds: list[BaseRound],
        score: int = 0,
        finished: bool = False,
        settings: Mapping[str, float] | None = None,
    ) -> None:
        self.id = id
        self.game_type = game_type
        self.mode = mode
        self.rounds = rounds
        self.score = score
        self.finished = finished
        # This game_type's live admin-configurable values (services/game_settings_service.py),
        # injected by GamesService. Read fresh on every request (see GamesService._game_kwargs),
        # never snapshotted onto a round, so a change takes effect on the very next round played
        # rather than only on new games.
        self._settings: Mapping[str, float] = settings or {}
        # Set by GamesService (never a constructor param - it's pure persistence metadata this
        # domain layer doesn't otherwise care about) right after building a daily game, to the
        # challenge's date. None for every normal game.
        self.daily_challenge_date: date | None = None

    @property
    def current_round(self) -> BaseRound:
        return self.rounds[-1]

    @property
    def total_rounds(self) -> int | None:
        """Live fixed round count, for games that have one (Geoguessr/Dateguessr) - None for every
        other game. Overridden by whoever has it; see api/dto/common.py's GameOut for why this is
        public. Living here (rather than an `isinstance` check in the DTO layer) is what lets each
        game define this independently without the DTO layer knowing which games happen to share
        the concept."""
        return None

    @property
    def total_people(self) -> int | None:
        """Live target headcount for WhosThatPerson - None for every other game. Same rationale as
        total_rounds above."""
        return None

    @property
    def face_box_growth(self) -> float | None:
        """Live face-box expansion factor for WhosThatPerson - None for every other game. Same
        rationale as total_rounds above."""
        return None

    def play_round(self, guess: Any) -> PlayRoundResult:
        if self.finished:
            raise ValueError("game is already finished")

        current = self.current_round
        current.guess = guess
        current.score_delta = current.calculate_score(self._settings)
        self.score += current.score_delta

        if self.has_next_round():
            self.rounds.append(self.create_next_round())
        else:
            self.finished = True

        return PlayRoundResult(score_delta=current.score_delta, score=self.score, finished=self.finished)

    @abstractmethod
    def has_next_round(self) -> bool:
        """Whether the game continues after the round that was just answered."""

    @abstractmethod
    def create_next_round(self) -> BaseRound:
        """Builds the next round, aware of previous rounds so it doesn't repeat candidates."""
