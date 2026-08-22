"""Registry mapping a Trivium mode to the question types it can ask - see
games/trivium/questions/base.py's QuestionType: a mode is a *topic*, not a single mechanic, so a
random type from the mode's list is picked round after round (no memory - the same type can repeat
back to back). The mixed mode is the union of every other mode's types plus its own two exclusive
ones (face -> name and name -> face), not a fourth independent list built from scratch."""

import random
from typing import Any
from uuid import UUID

from games.trivium.questions.base import GeneratedQuestion, QuestionType
from games.trivium.questions.birthday_day_month import BirthdayDayMonthQuestion
from games.trivium.questions.birthday_full_date import BirthdayFullDateQuestion
from games.trivium.questions.birthday_year import BirthYearQuestion
from games.trivium.questions.location_city import LocationCityQuestion
from games.trivium.questions.location_country import LocationCountryQuestion
from games.trivium.questions.mixed_face_to_name import MixedFaceToNameQuestion
from games.trivium.questions.mixed_name_to_face import MixedNameToFaceQuestion
from games.trivium.questions.photos_first_asset_year import PhotosFirstAssetYearQuestion
from games.trivium.questions.photos_together import PhotosTogetherQuestion
from games.trivium.questions.photos_total_assets import PhotosTotalAssetsQuestion
from services.immich import ContentQueries
from services.ml_service import MLService

MODE_BIRTHDAY = "birthday"
MODE_PHOTOS = "photos"
MODE_LOCATION = "location"
MODE_MIXED = "mixed"

MODES: dict[str, list[QuestionType]] = {
    MODE_BIRTHDAY: [BirthYearQuestion(), BirthdayDayMonthQuestion(), BirthdayFullDateQuestion()],
    MODE_PHOTOS: [PhotosTotalAssetsQuestion(), PhotosTogetherQuestion(), PhotosFirstAssetYearQuestion()],
    MODE_LOCATION: [LocationCountryQuestion(), LocationCityQuestion()],
}
MODES[MODE_MIXED] = [
    *MODES[MODE_BIRTHDAY],
    *MODES[MODE_PHOTOS],
    *MODES[MODE_LOCATION],
    MixedFaceToNameQuestion(),
    MixedNameToFaceQuestion(),
]


def pick_question(
    question_types: list[QuestionType], immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]
) -> GeneratedQuestion | None:
    """A random type from `question_types` that can currently generate a round - tries every type,
    in random order, before giving up. None means no type in this mode has enough content right
    now (a small library, an exhausted pool of subjects, ...)."""
    shuffled = list(question_types)
    random.shuffle(shuffled)
    for question_type in shuffled:
        question = question_type.generate(immich_service, exclude_subject_ids)
        if question is not None:
            return question
    return None


def extra_kwargs(content_source: ContentQueries, ml_service: MLService, mode: str) -> dict[str, Any]:
    """games/registry.py's GameSpec.extra_kwargs for TriviumGame - mode + this mode's question
    type bank, the role provider_factory/mode play for other multi-mode games (see
    games/registry.py's GameSpec docstring), just not expressed as a provider_factory since a
    mode's question types aren't bound to a ContentQueries."""
    return {"mode": mode, "question_types": MODES.get(mode, [])}
