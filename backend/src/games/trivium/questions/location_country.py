"""location_country question type - "in what country was this photo taken", subject: an asset
with a known location. Distractors are real countries that appear elsewhere in the library, never
invented strings."""

from uuid import UUID

from games.trivium.questions import _location_shared as shared
from games.trivium.questions.base import GeneratedQuestion
from services.immich import ContentQueries

KIND = "location_country"


class LocationCountryQuestion:
    def can_generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> bool:
        return shared.can_generate(immich_service, exclude_subject_ids, "country")

    def generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> GeneratedQuestion:
        return shared.generate(immich_service, exclude_subject_ids, "country", KIND)
