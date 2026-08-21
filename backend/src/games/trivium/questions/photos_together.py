"""photos_together question type - "who has the most photos with {person}", the correct answer
being whichever of 4 other named people co-occurs with the subject in the most assets. Like
photos_total_assets, the alternatives are real candidates (via
services/immich/persons.py's get_top_co_occurring_persons), not noise-generated values."""

import random
from uuid import UUID

from games.trivium.questions._shared import LIBRARY_SAMPLE_LIMIT
from games.trivium.questions.base import GeneratedQuestion, MediaSpec
from services.immich import ContentQueries

KIND = "photos_together"

Candidate = tuple[UUID, str, int]  # (person_id, person_name, co-occurrence count)


def _pick_candidates(immich_service: ContentQueries, subject_id: UUID) -> list[Candidate] | None:
    """The subject's top 4 co-occurring people, padded with random other named people (a real,
    if unqueried, 0 - they're excluded from the top-4 ranking entirely, so their true count can
    only be <= the last ranked one) when fewer than 4 people co-occur with the subject at all.
    None if there still aren't 4 distinct candidates, or the max isn't unique and > 0 - a 4-way
    tie, or everyone at 0, has no correct answer."""
    top = immich_service.get_top_co_occurring_persons(subject_id, limit=4)
    if len(top) < 4:
        exclude_ids = frozenset({person_id for person_id, _, _ in top} | {subject_id})
        needed = 4 - len(top)
        filler = immich_service.get_persons(named_only=True, randomize=True, limit=needed, exclude_ids=exclude_ids)
        if len(filler) < needed:
            return None
        top = [*top, *[(p.id, p.name, 0) for p in filler]]

    counts = [count for _, _, count in top]
    max_count = max(counts)
    if max_count <= 0 or counts.count(max_count) != 1:
        return None
    return top


def _find_subject_and_candidates(
    immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]
) -> tuple[UUID, str, list[Candidate]] | None:
    """Scans every eligible subject (shuffled, so repeated calls don't all try the same one
    first) until one yields a valid candidate set - whether a subject "works" depends on their
    specific co-occurrence data, so unlike birthday_year's library-wide range check, this can't be
    answered without actually trying subjects."""
    subjects = immich_service.get_persons(named_only=True, limit=LIBRARY_SAMPLE_LIMIT, exclude_ids=exclude_subject_ids)
    random.shuffle(subjects)
    for subject in subjects:
        candidates = _pick_candidates(immich_service, subject.id)
        if candidates is not None:
            return subject.id, subject.name, candidates
    return None


class PhotosTogetherQuestion:
    def can_generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> bool:
        return _find_subject_and_candidates(immich_service, exclude_subject_ids) is not None

    def generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> GeneratedQuestion:
        found = _find_subject_and_candidates(immich_service, exclude_subject_ids)
        if found is None:
            raise ValueError("no valid subject/candidates found - can_generate() should have returned False")
        subject_id, subject_name, candidates = found

        max_count = max(count for _, _, count in candidates)
        winner_id, winner_name = next((p_id, name) for p_id, name, count in candidates if count == max_count)

        alternatives: list[dict[str, str]] = [
            {"person_id": str(p_id), "person_name": name} for p_id, name, _ in candidates
        ]
        random.shuffle(alternatives)
        correct_value = {"person_id": str(winner_id), "person_name": winner_name}

        return GeneratedQuestion(
            question_kind=KIND,
            subject_id=subject_id,
            params={"person_id": str(subject_id), "person_name": subject_name},
            alternatives=alternatives,
            correct_index=alternatives.index(correct_value),
            media=MediaSpec(kind="person_thumbnail", person_id=subject_id),
        )
