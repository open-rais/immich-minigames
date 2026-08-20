"""Which open-report reasons exclude a candidate from Who'sThatPerson's live sampling, per mode -
see games/reports_registry.py for how this assembles with every other game's, and
services/reports_service.py for the wrapper that actually applies it."""

from games.report_spec import ReportReason
from games.whos_that_person.game import MODE_NAMED_FACES

REPORT_EXCLUSIONS: dict[str, frozenset[ReportReason]] = {
    MODE_NAMED_FACES: frozenset(
        {
            ReportReason.ASSET_FACE_MISMATCH,
            ReportReason.PERSON_NAME_FACE_MISMATCH,
            ReportReason.PERSON_NAME_SPELLING,
        }
    ),
}
