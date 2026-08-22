"""Which open-report reasons exclude a candidate from Trivium's live sampling, per mode - see
games/reports_registry.py for how this assembles with every other game's, and
services/reports_service.py for the wrapper that actually applies it.

`birthday` shows a named person and their real birth date, same underlying data as MoreOrLess'
personBirthDate mode - see games/more_or_less/reports.py for why those three reasons are the
right set for that shape of content. `photos` shows named people and how many/which photos they're
in, but never a birth date - same set as MoreOrLess' personAssets mode. `location` shows a photo
and asks about its location metadata - same reason Geoguessr's own mode excludes on, see
games/geoguessr/reports.py. `mixed` can generate any of the above plus its own two exclusive types
(face -> name, name -> face - both name/face content, no birth date or location on their own), so
its exclusions are the union of every other mode's."""

from games.report_spec import ReportReason
from games.trivium.modes import MODE_BIRTHDAY, MODE_LOCATION, MODE_MIXED, MODE_PHOTOS

REPORT_EXCLUSIONS: dict[str, frozenset[ReportReason]] = {
    MODE_BIRTHDAY: frozenset(
        {
            ReportReason.PERSON_NAME_FACE_MISMATCH,
            ReportReason.PERSON_NAME_SPELLING,
            ReportReason.PERSON_BIRTH_DATE,
        }
    ),
    MODE_PHOTOS: frozenset({ReportReason.PERSON_NAME_FACE_MISMATCH, ReportReason.PERSON_NAME_SPELLING}),
    MODE_LOCATION: frozenset({ReportReason.ASSET_LOCATION}),
}
REPORT_EXCLUSIONS[MODE_MIXED] = frozenset().union(*REPORT_EXCLUSIONS.values())
