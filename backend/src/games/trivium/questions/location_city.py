"""location_city question type - "in what city was this photo taken", subject: an asset with a
known location. Distractors are real cities that appear elsewhere in the library, never invented
strings."""

from uuid import UUID

from games.trivium.questions import _location_shared as shared
from games.trivium.questions.base import GeneratedQuestion
from services.immich import ContentQueries

KIND = "location_city"


class LocationCityQuestion:
    def can_generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> bool:
        return shared.can_generate(immich_service, exclude_subject_ids, "city")

    def generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> GeneratedQuestion:
        return shared.generate(immich_service, exclude_subject_ids, "city", KIND)
