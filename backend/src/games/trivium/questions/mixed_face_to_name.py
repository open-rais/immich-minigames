"""mixed_face_to_name question type - "what's this person's name", subject: a random named person
shown as a face. Alternatives are 4 real names (never invented) - the correct one plus 3 other
people's, guaranteed distinct so the correct answer is never ambiguous between two same-named
people. Exclusive to the mixed mode - see games/trivium/modes.py."""

import random
from uuid import UUID

from domain.person import Person
from games.trivium.questions.base import GeneratedQuestion, MediaSpec
from services.immich import ContentQueries

KIND = "mixed_face_to_name"

_CANDIDATE_POOL_LIMIT = 50
_MAX_ATTEMPTS = 20


def _pick_group(
    immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]
) -> tuple[Person, list[Person]] | None:
    pool = immich_service.get_persons(named_only=True, randomize=True, limit=_CANDIDATE_POOL_LIMIT)
    eligible_subjects = [p for p in pool if p.id not in exclude_subject_ids]
    if not eligible_subjects or len(pool) < 4:
        return None
    for _ in range(_MAX_ATTEMPTS):
        subject = random.choice(eligible_subjects)
        others = [p for p in pool if p.id != subject.id]
        if len(others) < 3:
            return None
        distractors = random.sample(others, 3)
        # A real family library can plausibly have two people who share a name (relatives named
        # after each other) - since the alternatives here are bare name strings, not person_ids, a
        # collision would make the correct one ambiguous (or silently wrong via list.index()).
        if len({subject.name, *(d.name for d in distractors)}) == 4:
            return subject, distractors
    return None


class MixedFaceToNameQuestion:
    def can_generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> bool:
        return _pick_group(immich_service, exclude_subject_ids) is not None

    def generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> GeneratedQuestion:
        found = _pick_group(immich_service, exclude_subject_ids)
        if found is None:
            raise ValueError("no valid subject/distractor group found - can_generate() should have returned False")
        subject, distractors = found

        alternatives: list[str] = [subject.name, *(d.name for d in distractors)]
        random.shuffle(alternatives)

        return GeneratedQuestion(
            question_kind=KIND,
            subject_id=subject.id,
            # No {persona} to interpolate - the question is "what's THIS person's name", answered
            # entirely by the shown face (media below) and the alternatives, not by params.
            params={},
            alternatives=alternatives,
            correct_index=alternatives.index(subject.name),
            media=MediaSpec(kind="person_thumbnail", person_id=subject.id),
        )
