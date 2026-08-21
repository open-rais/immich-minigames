"""photos_total_assets question type - "which of these people has the most photos overall", the
correct answer being whichever of 4 named candidates has the (uniquely) highest asset_count. No
noise-based distractors here (unlike the birthday_*/photos_first_asset_year types): the 3 wrong
alternatives are the other 3 real candidates, exactly like MoreOrLess's personAssets mode compares
real asset_count values rather than invented ones."""

import random
from uuid import UUID

from domain.person import Person
from games.trivium.questions.base import GeneratedQuestion, MediaSpec
from services.immich import ContentQueries

KIND = "photos_total_assets"

# How many named people to sample candidate groups of 4 from, and how many distinct groups to try
# before giving up - a tie for the max (or the winner already being excluded) just means trying a
# different group of 4 from the same pool, not a new query.
_CANDIDATE_POOL_LIMIT = 50
_MAX_ATTEMPTS = 20


def _sample_group(immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> list[Person] | None:
    pool = immich_service.get_persons(named_only=True, randomize=True, limit=_CANDIDATE_POOL_LIMIT)
    if len(pool) < 4:
        return None
    for _ in range(_MAX_ATTEMPTS):
        group = random.sample(pool, 4)
        max_count = max(p.asset_count for p in group)
        winner = next(p for p in group if p.asset_count == max_count)
        # The max must be unique (a tie has no correct answer) and the winner - this type's
        # subject, see the module docstring - mustn't repeat one already used this game.
        if sum(1 for p in group if p.asset_count == max_count) == 1 and winner.id not in exclude_subject_ids:
            return group
    return None


class PhotosTotalAssetsQuestion:
    def can_generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> bool:
        return _sample_group(immich_service, exclude_subject_ids) is not None

    def generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> GeneratedQuestion:
        group = _sample_group(immich_service, exclude_subject_ids)
        if group is None:
            raise ValueError("no valid candidate group found - can_generate() should have returned False")
        max_count = max(p.asset_count for p in group)
        winner = next(p for p in group if p.asset_count == max_count)

        alternatives: list[dict[str, str]] = [{"person_id": str(p.id), "person_name": p.name} for p in group]
        random.shuffle(alternatives)
        correct_value = {"person_id": str(winner.id), "person_name": winner.name}

        return GeneratedQuestion(
            question_kind=KIND,
            subject_id=winner.id,
            # No {persona} in this question's phrasing (see the doc) - it's entirely about the 4
            # alternatives, so there's nothing to interpolate.
            params={},
            alternatives=alternatives,
            correct_index=alternatives.index(correct_value),
            media=MediaSpec(kind="none"),
        )
