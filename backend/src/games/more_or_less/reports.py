"""Which open-report reasons exclude a candidate from MoreOrLess's live sampling, per mode - see
games/reports_registry.py for how this assembles with every other game's, and
services/reports_service.py for the wrapper that actually applies it."""

from games.more_or_less.game import MODE_ALBUM_ASSETS, MODE_PERSON_ASSETS, MODE_PERSON_BIRTH_DATE
from games.report_spec import ReportReason

REPORT_EXCLUSIONS: dict[str, frozenset[ReportReason]] = {
    MODE_PERSON_ASSETS: frozenset({ReportReason.PERSON_NAME_FACE_MISMATCH, ReportReason.PERSON_NAME_SPELLING}),
    MODE_ALBUM_ASSETS: frozenset({ReportReason.ALBUM_COVER_MISMATCH, ReportReason.ALBUM_NAME_SPELLING}),
    # Plus the person's own two, since a candidate is shown by name and photo here too.
    MODE_PERSON_BIRTH_DATE: frozenset(
        {
            ReportReason.PERSON_NAME_FACE_MISMATCH,
            ReportReason.PERSON_NAME_SPELLING,
            ReportReason.PERSON_BIRTH_DATE,
        }
    ),
}
