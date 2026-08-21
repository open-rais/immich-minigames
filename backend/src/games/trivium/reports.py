"""Which open-report reasons exclude a candidate from Trivium's live sampling, per mode - see
games/reports_registry.py for how this assembles with every other game's, and
services/reports_service.py for the wrapper that actually applies it.

`birthday` shows a named person and their real birth date, same underlying data as MoreOrLess'
personBirthDate mode - see games/more_or_less/reports.py for why those three reasons are the
right set for that shape of content."""

from games.report_spec import ReportReason
from games.trivium.modes import MODE_BIRTHDAY

REPORT_EXCLUSIONS: dict[str, frozenset[ReportReason]] = {
    MODE_BIRTHDAY: frozenset(
        {
            ReportReason.PERSON_NAME_FACE_MISMATCH,
            ReportReason.PERSON_NAME_SPELLING,
            ReportReason.PERSON_BIRTH_DATE,
        }
    ),
}
