from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

from domain.person import Person
from services.notifications.content import todays_album_anniversaries, todays_birthdays


@dataclass
class _FakeImmichService:
    birthday_persons: list[Person] = field(default_factory=list)
    starting_albums: list[tuple[UUID, str, date]] = field(default_factory=list)

    def get_persons_with_birthday_on(self, month: int, day: int) -> list[Person]:
        return self.birthday_persons

    def get_albums_starting_on(self, month: int, day: int) -> list[tuple[UUID, str, date]]:
        return self.starting_albums


@dataclass
class _FakeExclusions:
    person_ids: frozenset[UUID] = frozenset()


@dataclass
class _FakeReportsService:
    excluded_person_ids: frozenset[UUID] = frozenset()

    def open_ids_for(self, reasons):
        return _FakeExclusions(person_ids=self.excluded_person_ids)


def _person(name: str, birth_year: int, person_id: UUID | None = None) -> Person:
    return Person(id=person_id or uuid4(), name=name, birth_date=date(birth_year, 6, 15), asset_count=3)


class TestTodaysBirthdays:
    def test_computes_age_from_birth_year(self):
        immich = _FakeImmichService(birthday_persons=[_person("María", 1990)])
        entries = todays_birthdays(immich, _FakeReportsService(), date(2026, 6, 15))

        assert len(entries) == 1
        assert entries[0].name == "María"
        assert entries[0].age == 36

    def test_discards_a_non_positive_age(self):
        # A birth year in the future (or this same year) means the stored date is wrong, not a
        # newborn worth congratulating on Immich's own upload day.
        immich = _FakeImmichService(birthday_persons=[_person("Recién Nacido", 2026)])
        entries = todays_birthdays(immich, _FakeReportsService(), date(2026, 6, 15))

        assert entries == []

    def test_excludes_a_person_with_an_open_birth_date_report(self):
        reported = _person("Reportado", 1980)
        immich = _FakeImmichService(birthday_persons=[reported, _person("Sin Reporte", 1980)])
        reports = _FakeReportsService(excluded_person_ids=frozenset({reported.id}))

        entries = todays_birthdays(immich, reports, date(2026, 6, 15))

        assert [e.name for e in entries] == ["Sin Reporte"]

    def test_no_matching_persons_returns_an_empty_list(self):
        immich = _FakeImmichService(birthday_persons=[])
        assert todays_birthdays(immich, _FakeReportsService(), date(2026, 6, 15)) == []


class TestTodaysAlbumAnniversaries:
    def test_computes_years_ago_from_the_first_asset_date(self):
        immich = _FakeImmichService(starting_albums=[(uuid4(), "Verano 2020", date(2020, 6, 15))])
        entries = todays_album_anniversaries(immich, date(2026, 6, 15))

        assert len(entries) == 1
        assert entries[0].name == "Verano 2020"
        assert entries[0].years_ago == 6

    def test_discards_an_album_that_started_this_same_year(self):
        immich = _FakeImmichService(starting_albums=[(uuid4(), "Este Año", date(2026, 6, 15))])
        assert todays_album_anniversaries(immich, date(2026, 6, 15)) == []

    def test_no_matching_albums_returns_an_empty_list(self):
        immich = _FakeImmichService(starting_albums=[])
        assert todays_album_anniversaries(immich, date(2026, 6, 15)) == []
