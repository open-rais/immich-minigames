"""Trivium's question-type bank - see questions/base.py for the QuestionType contract every module
here implements, and games/trivium/modes.py for which types each mode enables. Re-exports the
public surface so `from games.trivium.questions import BirthYearQuestion` (the mode registry,
tests) keeps working unchanged."""

from games.trivium.questions.base import GeneratedQuestion, MediaKind, MediaSpec, QuestionType
from games.trivium.questions.birthday_year import BirthYearQuestion

__all__ = [
    "BirthYearQuestion",
    "GeneratedQuestion",
    "MediaKind",
    "MediaSpec",
    "QuestionType",
]
