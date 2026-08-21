"""photos_together question type - "which of these people has the most photos with {person}",
the correct answer being whichever of 4 other named people co-occurs with the subject in the most
assets. Like photos_total_assets, the alternatives are real candidates (via
services/immich/persons.py's get_top_co_occurring_persons), not noise-generated values."""

import random
from uuid import UUID

from games.trivium.questions._shared import LIBRARY_SAMPLE_LIMIT
from games.trivium.questions.base import GeneratedQuestion, MediaSpec
from services.immich import ContentQueries

KIND = "photos_together"

Candidate = tuple[UUID, str, int]  # (person_id, person_name, co-occurrence count)

# How many of the subject's co-occurring people to sample candidate groups of 4 from - a pool to
# pick a *random* 4 out of, not a fixed top-4 (confirmed by the owner: the correct answer
# shouldn't always be whoever has the single highest count with the subject). How many distinct
# groups to try before giving up on this subject.
_CANDIDATE_POOL_LIMIT = 20
_MAX_ATTEMPTS = 20


def _pick_candidates(immich_service: ContentQueries, subject_id: UUID) -> list[Candidate] | None:
    """4 candidates who co-occur with the subject, drawn at random from up to
    _CANDIDATE_POOL_LIMIT of them (ranked only to cap the query, not to always surface the top 4),
    padded with random other named people (a real, if unqueried, 0 - they're outside the ranked
    pool entirely, so their true count can only be <= its lowest) when fewer than 4 co-occur at
    all. None if no group of 4 has a unique, positive max after _MAX_ATTEMPTS tries - a 4-way tie,
    or everyone at 0, has no correct answer."""
    pool = immich_service.get_top_co_occurring_persons(subject_id, limit=_CANDIDATE_POOL_LIMIT)
    if len(pool) < 4:
        exclude_ids = frozenset({person_id for person_id, _, _ in pool} | {subject_id})
        needed = 4 - len(pool)
        filler = immich_service.get_persons(named_only=True, randomize=True, limit=needed, exclude_ids=exclude_ids)
        if len(filler) < needed:
            return None
        pool = [*pool, *[(p.id, p.name, 0) for p in filler]]

    for _ in range(_MAX_ATTEMPTS):
        candidates = random.sample(pool, 4)
        counts = [count for _, _, count in candidates]
        max_count = max(counts)
        if max_count > 0 and counts.count(max_count) == 1:
            return candidates
    return None


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
