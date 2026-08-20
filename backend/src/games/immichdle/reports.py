"""Which open-report reasons exclude a candidate from Immichdle's live sampling, per mode - see
games/reports_registry.py for how this assembles with every other game's, and
services/reports_service.py for the wrapper that actually applies it."""

from games.immichdle.game import MODE_ALBUM, MODE_PERSON
from games.report_spec import ReportReason

REPORT_EXCLUSIONS: dict[str, frozenset[ReportReason]] = {
    MODE_PERSON: frozenset(
        {
            ReportReason.PERSON_BIRTH_DATE,
            ReportReason.PERSON_NAME_FACE_MISMATCH,
            ReportReason.PERSON_NAME_SPELLING,
        }
    ),
    MODE_ALBUM: frozenset({ReportReason.ALBUM_COVER_MISMATCH, ReportReason.ALBUM_NAME_SPELLING}),
}
