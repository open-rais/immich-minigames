"""What's notifiable today, for the 12:00 birthdays and 14:00 album-anniversary notifications -
installation-wide facts (unlike the 10:00/21:00 daily reminders, which are per-user), computed
once per tick and fanned out to every subscribed user with the matching preference on (see
schedule.py). Both queries are read straight off Immich (services/immich/), the exclusion of
open, relevant reports is this module's own job.
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from services.immich import ImmichService
from services.reports_service import ReportsService


@dataclass(frozen=True)
class BirthdayEntry:
    person_id: UUID
    name: str
    age: int


@dataclass(frozen=True)
class AlbumAnniversaryEntry:
    album_id: UUID
    name: str
    years_ago: int


def todays_birthdays(
    immich_service: ImmichService, reports_service: ReportsService, today: date
) -> list[BirthdayEntry]:
    """Named, non-hidden people whose birthDate falls on today's month/day, any year, excluding
    anyone with an open person_birth_date report (that date is exactly what's in question) and
    anyone whose computed age comes out <= 0 (a birth year that hasn't happened yet, or this year -
    both mean the stored date is wrong, not a reason to congratulate a newborn on Immich's own
    upload day)."""
    excluded = reports_service.open_ids_for(["person_birth_date"]).person_ids
    entries = []
    for person in immich_service.get_persons_with_birthday_on(today.month, today.day):
        if person.id in excluded or person.birth_date is None:
            continue
        age = today.year - person.birth_date.year
        if age <= 0:
            continue
        entries.append(BirthdayEntry(person_id=person.id, name=person.name, age=age))
    return entries


def todays_album_anniversaries(immich_service: ImmichService, today: date) -> list[AlbumAnniversaryEntry]:
    """Albums whose earliest eligible asset's local day falls on today's month/day, any year prior
    to this one. No open-report exclusion here (unlike birthdays) - there is currently no
    ReportReason capturing "this album's date is wrong" (only album_cover_mismatch/
    album_name_spelling exist), and adding one is a reporting-feature change of its own, out of
    scope for this notification."""
    entries = []
    for album_id, name, first_asset_date in immich_service.get_albums_starting_on(today.month, today.day):
        years_ago = today.year - first_asset_date.year
        if years_ago < 1:
            continue
        entries.append(AlbumAnniversaryEntry(album_id=album_id, name=name, years_ago=years_ago))
    return entries
