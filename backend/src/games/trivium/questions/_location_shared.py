"""Shared plumbing for Trivium's location_country/location_city question types - both pick a
subject asset the same way (categorical anti-repetition over games/shared/picking.py's
pick_spread_asset) and differ only in which asset_exif field (country vs city) they read/distract
on. Not shared with any other game - same narrower-than-games/shared/ boundary
games/trivium/questions/_shared.py's docstring already draws for the birthday_* trio."""

import random
from typing import Literal
from uuid import UUID

from domain.asset import Asset
from games.shared.picking import pick_spread_asset
from games.trivium.questions.base import GeneratedQuestion, MediaSpec
from services.immich import ContentQueries

Field = Literal["country", "city"]

# How many random located photos to sample when looking for a subject whose country/city differs
# from every previous round's - see pick_spread_asset. Not required for correctness (falls back to
# the first candidate if none qualifies) - just keeps rounds spread across places instead of
# clustering on the library's most-photographed one.
_CANDIDATE_SAMPLE_SIZE = 20


def _field_value(asset: Asset, field: Field) -> str | None:
    return asset.country if field == "country" else asset.city


def _previous_values(immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID], field: Field) -> list[str]:
    """The country/city of every subject already used this game - exclude_subject_ids is exactly
    that set of asset ids (games/trivium/game.py's TriviumGame._used_subject_ids), since location
    mode's subjects are never anything but assets."""
    if not exclude_subject_ids:
        return []
    previous_assets = immich_service.get_assets(ids=exclude_subject_ids, limit=len(exclude_subject_ids))
    return [value for a in previous_assets if (value := _field_value(a, field)) is not None]


def _pick_subject(immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID], field: Field) -> Asset | None:
    candidates = [
        a
        for a in immich_service.get_assets(
            media_type="photo",
            with_location=True,
            randomize=True,
            limit=_CANDIDATE_SAMPLE_SIZE,
            exclude_ids=exclude_subject_ids,
        )
        if _field_value(a, field) is not None
    ]
    if not candidates:
        return None

    def separation(candidate: Asset, previous_value: str) -> float:
        return 1.0 if _field_value(candidate, field) != previous_value else 0.0

    previous_values = _previous_values(immich_service, exclude_subject_ids, field)
    return pick_spread_asset(candidates, previous_values, separation, min_separation=1.0)


def generate(
    immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID], field: Field, question_kind: str
) -> GeneratedQuestion | None:
    # A closed set of >= 4 distinct real values always leaves >= 3 to use as distractors besides
    # whichever one turns out to be correct - a realistic risk for country in a family library
    # confined to a handful of countries, unlikely but not impossible for city too. Fetched once,
    # up front: also the pool the distractors are drawn from below, so there's no reason to ask
    # Immich for it twice.
    distinct = immich_service.get_distinct_locations(field)
    if len(distinct) < 4:
        return None
    subject = _pick_subject(immich_service, exclude_subject_ids, field)
    if subject is None:
        return None
    correct = _field_value(subject, field)
    assert correct is not None  # _pick_subject only ever returns assets with a real value

    distractors = random.sample([v for v in distinct if v != correct], 3)

    alternatives: list[str] = [*distractors, correct]
    random.shuffle(alternatives)

    return GeneratedQuestion(
        question_kind=question_kind,
        subject_id=subject.id,
        # No {persona}/named subject to interpolate - "in what country was this photo taken" needs
        # nothing beyond the photo itself, shown via media below.
        params={},
        alternatives=alternatives,
        correct_index=alternatives.index(correct),
        media=MediaSpec(kind="asset", asset_id=subject.id),
    )
