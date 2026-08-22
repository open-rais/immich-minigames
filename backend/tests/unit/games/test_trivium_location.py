"""Trivium's `location` mode question types. Happy-path generation is tested against the real dev
Immich Postgres (see tests/conftest.py) - the "library doesn't give enough" and anti-repetition
edge cases need data/sequences this app's actual dev fixtures don't reliably contain, so those use
a small in-memory ContentQueries double instead."""

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID, uuid4

from domain.asset import Asset
from games.trivium.questions.base import GeneratedQuestion
from games.trivium.questions.location_city import KIND as CITY_KIND
from games.trivium.questions.location_city import LocationCityQuestion
from games.trivium.questions.location_country import KIND as COUNTRY_KIND
from games.trivium.questions.location_country import LocationCountryQuestion


def _asset(country: str | None = None, city: str | None = None) -> Asset:
    return Asset(
        id=uuid4(),
        type="IMAGE",
        file_created_at=datetime(2020, 1, 1),
        local_date=date(2020, 1, 1),
        original_file_name="",
        width=None,
        height=None,
        is_favorite=False,
        latitude=0.0,
        longitude=0.0,
        city=city,
        state=None,
        country=country,
    )


@dataclass
class _FakeImmich:
    """Minimal ContentQueries double - a plain in-memory asset pool, filtered/resolved the way
    the real ImmichService methods behave for the arguments these question types actually pass."""

    assets: list[Asset] = field(default_factory=list)

    def get_assets(
        self,
        *,
        with_location: bool | None = None,
        limit: int = 1,
        ids: frozenset[UUID] | None = None,
        exclude_ids: frozenset[UUID] = frozenset(),
        **kwargs,
    ) -> list[Asset]:
        pool = self.assets
        if ids is not None:
            pool = [a for a in pool if a.id in ids]
        if with_location is True:
            pool = [a for a in pool if a.latitude is not None]
        pool = [a for a in pool if a.id not in exclude_ids]
        return pool[:limit]

    def get_distinct_locations(self, field: str) -> list[str]:
        return list({getattr(a, field) for a in self.assets if getattr(a, field)})


class TestLocationCountryQuestionAgainstRealData:
    def test_generate_succeeds_with_the_dev_library(self, immich_service):
        assert LocationCountryQuestion().generate(immich_service, frozenset()) is not None

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question = LocationCountryQuestion().generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == COUNTRY_KIND
        assert len(question.alternatives) == 4
        assert len(set(question.alternatives)) == 4
        assert 0 <= question.correct_index < 4
        assert question.params == {}
        assert question.media.kind == "asset"
        assert question.media.asset_id == question.subject_id

    def test_the_correct_alternative_is_the_subjects_real_country(self, immich_service):
        question = LocationCountryQuestion().generate(immich_service, frozenset())
        [subject] = immich_service.get_assets(ids=frozenset({question.subject_id}))
        assert question.alternatives[question.correct_index] == subject.country

    def test_distractors_are_real_countries_from_the_library(self, immich_service):
        real_countries = set(immich_service.get_distinct_locations("country"))
        question = LocationCountryQuestion().generate(immich_service, frozenset())
        assert set(question.alternatives) <= real_countries

    def test_excluding_every_located_asset_makes_it_ungeneratable(self, immich_service):
        located = immich_service.get_assets(with_location=True, limit=10_000)
        all_ids = frozenset(a.id for a in located)
        assert LocationCountryQuestion().generate(immich_service, all_ids) is None


class TestLocationCityQuestionAgainstRealData:
    def test_generate_succeeds_with_the_dev_library(self, immich_service):
        assert LocationCityQuestion().generate(immich_service, frozenset()) is not None

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question = LocationCityQuestion().generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == CITY_KIND
        assert len(question.alternatives) == 4
        assert len(set(question.alternatives)) == 4
        assert question.media.kind == "asset"


class TestLocationEdgeCases:
    def test_generate_returns_none_with_fewer_than_four_distinct_countries(self):
        assets = [_asset(country="Chile"), _asset(country="Chile"), _asset(country="Argentina")]
        immich = _FakeImmich(assets=assets)

        assert LocationCountryQuestion().generate(immich, frozenset()) is None

    def test_generate_returns_none_with_no_located_assets_at_all(self):
        immich = _FakeImmich(assets=[])
        assert LocationCountryQuestion().generate(immich, frozenset()) is None

    def test_avoids_repeating_the_previous_rounds_country_while_an_alternative_exists(self):
        chile_assets = [_asset(country="Chile") for _ in range(3)]
        other = [_asset(country=c) for c in ["Argentina", "France", "Spain"]]
        immich = _FakeImmich(assets=[*chile_assets, *other])

        first = LocationCountryQuestion().generate(immich, frozenset())
        first_correct = first.alternatives[first.correct_index]

        second = LocationCountryQuestion().generate(immich, frozenset({first.subject_id}))
        second_correct = second.alternatives[second.correct_index]

        assert second_correct != first_correct

    def test_repeats_the_country_once_no_other_one_is_available(self):
        chile_assets = [_asset(country="Chile") for _ in range(3)]
        other = [_asset(country=c) for c in ["Argentina", "France", "Spain"]]
        immich = _FakeImmich(assets=[*chile_assets, *other])
        # A previous round already used one Chile asset, and every non-Chile asset has ALSO
        # already been used - only more Chile assets are left, so the categorical spread has to
        # give up and repeat Chile (games/shared/picking.py's pick_spread_asset fallback) rather
        # than leaving the mode stuck.
        used_ids = frozenset({chile_assets[0].id, other[0].id, other[1].id, other[2].id})

        question = LocationCountryQuestion().generate(immich, used_ids)

        assert question.alternatives[question.correct_index] == "Chile"
