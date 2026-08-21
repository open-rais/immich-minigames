"""Registry mapping a Trivium mode to the question types it can ask - see
games/trivium/questions/base.py's QuestionType and TRIVIUM.md §2.5: a mode is a *topic*, not a
single mechanic, so ronda a ronda a random type from the mode's list is picked (no memory - the
same type can repeat back to back, confirmed by the owner in §2.5). Only `birthday` is populated
in this phase (TRIVIUM.md's F1) - location/photos (F3/F4) each add their own entry, and mixed (F5)
becomes the union of every other mode's types plus its own two exclusive ones, not a fourth
independent list built from scratch."""

import random
from uuid import UUID

from games.trivium.questions.base import GeneratedQuestion, QuestionType
from games.trivium.questions.birthday_year import BirthYearQuestion
from services.immich import ContentQueries

MODE_BIRTHDAY = "birthday"

MODES: dict[str, list[QuestionType]] = {
    MODE_BIRTHDAY: [BirthYearQuestion()],
}


def pick_question(
    question_types: list[QuestionType], immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]
) -> GeneratedQuestion | None:
    """A random type from `question_types` that can currently generate a round - tries every type,
    in random order, before giving up (TRIVIUM.md §2.5's "no puedo generar ronda ahora" fallback).
    None means no type in this mode has enough content right now."""
    shuffled = list(question_types)
    random.shuffle(shuffled)
    for question_type in shuffled:
        if question_type.can_generate(immich_service, exclude_subject_ids):
            return question_type.generate(immich_service, exclude_subject_ids)
    return None


def any_question_available(
    question_types: list[QuestionType], immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]
) -> bool:
    return any(q.can_generate(immich_service, exclude_subject_ids) for q in question_types)
