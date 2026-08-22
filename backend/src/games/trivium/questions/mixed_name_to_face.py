"""mixed_name_to_face question type - "who is {person}", subject: a random named person shown by
name only. Alternatives are 4 real faces (the correct person plus 3 others) - the inverse of
mixed_face_to_name. Exclusive to the mixed mode - see games/trivium/modes.py."""

import random
from uuid import UUID

from games.trivium.questions.base import GeneratedQuestion, MediaSpec
from services.immich import ContentQueries

KIND = "mixed_name_to_face"

_CANDIDATE_POOL_LIMIT = 50


class MixedNameToFaceQuestion:
    def generate(
        self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]
    ) -> GeneratedQuestion | None:
        candidates = immich_service.get_persons(
            named_only=True, randomize=True, limit=1, exclude_ids=exclude_subject_ids
        )
        if not candidates:
            return None
        subject = candidates[0]
        others = immich_service.get_persons(
            named_only=True, randomize=True, limit=_CANDIDATE_POOL_LIMIT, exclude_ids=frozenset({subject.id})
        )
        if len(others) < 3:
            return None
        distractors = random.sample(others, 3)

        candidates = [subject, *distractors]
        alternatives: list[dict[str, str]] = [{"person_id": str(p.id), "person_name": p.name} for p in candidates]
        random.shuffle(alternatives)
        correct_value = {"person_id": str(subject.id), "person_name": subject.name}

        return GeneratedQuestion(
            question_kind=KIND,
            subject_id=subject.id,
            params={"person_id": str(subject.id), "person_name": subject.name},
            alternatives=alternatives,
            correct_index=alternatives.index(correct_value),
            # No media on the question card itself - the "sample" here is the name (already in
            # params, rendered as question text), not a photo. The photos are the alternatives.
            media=MediaSpec(kind="none"),
        )
