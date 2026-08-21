"""Trivium - see games/trivium/game.py. Re-exports the public surface so `from games.trivium
import TriviumGame` (external callers, tests) keeps working unchanged."""

from games.trivium.game import GAME_TYPE, MAX_ROUNDS, TriviumGame
from games.trivium.modes import MODE_BIRTHDAY, MODES
from games.trivium.questions.base import GeneratedQuestion, MediaKind, MediaSpec, QuestionType
from games.trivium.questions.birthday_year import BirthYearQuestion
from games.trivium.round import ANSWER_TIME_SECONDS, MAX_POINTS, Answer, TriviumRound

__all__ = [
    "ANSWER_TIME_SECONDS",
    "GAME_TYPE",
    "MAX_POINTS",
    "MAX_ROUNDS",
    "MODE_BIRTHDAY",
    "MODES",
    "Answer",
    "BirthYearQuestion",
    "GeneratedQuestion",
    "MediaKind",
    "MediaSpec",
    "QuestionType",
    "TriviumGame",
    "TriviumRound",
]
