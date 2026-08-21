"""Trivium's `photos` mode question types. Happy-path generation is tested against the real dev
Immich Postgres (see tests/conftest.py) - the "library doesn't give enough" edge cases (no unique
max, co-occurrence entirely 0) need data this app's actual dev fixtures don't reliably contain, so
those use a small in-memory ContentQueries double instead."""

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

from domain.person import Person
from games.trivium.questions.base import GeneratedQuestion
from games.trivium.questions.photos_first_asset_year import KIND as FIRST_ASSET_YEAR_KIND
from games.trivium.questions.photos_first_asset_year import PhotosFirstAssetYearQuestion
from games.trivium.questions.photos_together import KIND as TOGETHER_KIND
from games.trivium.questions.photos_together import PhotosTogetherQuestion
from games.trivium.questions.photos_total_assets import KIND as TOTAL_ASSETS_KIND
from games.trivium.questions.photos_total_assets import PhotosTotalAssetsQuestion


def _person(name: str, asset_count: int = 0, birth_date: date | None = None) -> Person:
    return Person(id=uuid4(), name=name, birth_date=birth_date, asset_count=asset_count)


@dataclass
class _FakeImmich:
    """Minimal ContentQueries double - a plain in-memory person pool plus canned
    co-occurrence/first-asset-date lookups, filtered the way the real ImmichService methods behave
    for the arguments these question types actually pass."""

    persons: list[Person] = field(default_factory=list)
    co_occurrence: dict[UUID, list[tuple[UUID, str, int]]] = field(default_factory=dict)
    first_asset_dates: dict[UUID, date] = field(default_factory=dict)

    def get_persons(
        self,
        *,
        named_only: bool = True,
        with_birthdate: bool | None = None,
        randomize: bool = False,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
        ids: frozenset[UUID] | None = None,
        **kwargs,
    ) -> list[Person]:
        pool = self.persons
        if ids is not None:
            pool = [p for p in pool if p.id in ids]
        if with_birthdate is True:
            pool = [p for p in pool if p.birth_date is not None]
        elif with_birthdate is False:
            pool = [p for p in pool if p.birth_date is None]
        pool = [p for p in pool if p.id not in exclude_ids]
        return pool[:limit]

    def get_top_co_occurring_persons(
        self, person_id: UUID, *, limit: int = 3, exclude_ids: frozenset[UUID] = frozenset()
    ) -> list[tuple[UUID, str, int]]:
        rows = [row for row in self.co_occurrence.get(person_id, []) if row[0] not in exclude_ids]
        return rows[:limit]

    def get_person_first_asset_date(self, person_id: UUID) -> date | None:
        return self.first_asset_dates.get(person_id)


class TestPhotosTotalAssetsQuestionAgainstRealData:
    def test_can_generate_is_true_with_the_dev_library(self, immich_service):
        assert PhotosTotalAssetsQuestion().can_generate(immich_service, frozenset())

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question = PhotosTotalAssetsQuestion().generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == TOTAL_ASSETS_KIND
        assert len(question.alternatives) == 4
        ids = {alt["person_id"] for alt in question.alternatives}
        assert len(ids) == 4  # 4 distinct candidates
        assert str(question.subject_id) in ids
        assert question.media.kind == "none"

    def test_the_correct_alternative_has_the_highest_asset_count(self, immich_service):
        question = PhotosTotalAssetsQuestion().generate(immich_service, frozenset())
        candidate_ids = frozenset(UUID(alt["person_id"]) for alt in question.alternatives)
        candidates = immich_service.get_persons(named_only=True, ids=candidate_ids, limit=10)
        by_id = {p.id: p for p in candidates}

        correct_id = UUID(question.alternatives[question.correct_index]["person_id"])
        winner_count = by_id[correct_id].asset_count
        assert all(p.asset_count <= winner_count for p in candidates)
        assert sum(1 for p in candidates if p.asset_count == winner_count) == 1


class TestPhotosTotalAssetsQuestionEdgeCases:
    def test_can_generate_is_false_with_fewer_than_four_people(self):
        immich = _FakeImmich(persons=[_person("A", 5), _person("B", 3), _person("C", 1)])
        assert PhotosTotalAssetsQuestion().can_generate(immich, frozenset()) is False

    def test_can_generate_is_false_when_no_group_of_four_has_a_unique_max(self):
        # Every person has the exact same asset_count - any group of 4 ties at the top.
        immich = _FakeImmich(persons=[_person(f"P{i}", asset_count=10) for i in range(6)])
        assert PhotosTotalAssetsQuestion().can_generate(immich, frozenset()) is False

    def test_a_previously_used_winner_is_not_reoffered_as_the_correct_answer(self):
        # One person (the max) plus 5 tied-for-second - the only possible unique-max winner is
        # excluded, so no valid group of 4 can be formed.
        winner = _person("Winner", asset_count=100)
        immich = _FakeImmich(persons=[winner, *[_person(f"P{i}", asset_count=5) for i in range(5)]])
        assert PhotosTotalAssetsQuestion().can_generate(immich, frozenset({winner.id})) is False


class TestPhotosTogetherQuestionAgainstRealData:
    def test_can_generate_is_true_with_the_dev_library(self, immich_service):
        assert PhotosTogetherQuestion().can_generate(immich_service, frozenset())

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question = PhotosTogetherQuestion().generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == TOGETHER_KIND
        assert len(question.alternatives) == 4
        assert len({alt["person_id"] for alt in question.alternatives}) == 4
        assert question.params["person_id"] == str(question.subject_id)
        assert question.media.kind == "person_thumbnail"
        assert question.media.person_id == question.subject_id
        # The subject is never one of their own candidates.
        assert str(question.subject_id) not in {alt["person_id"] for alt in question.alternatives}


class TestPhotosTogetherQuestionEdgeCases:
    def test_can_generate_is_false_when_co_occurrence_is_all_zero(self):
        subject = _person("Subject")
        others = [_person(f"P{i}") for i in range(6)]
        # No co_occurrence entries at all for `subject` - _pick_candidates pads entirely with
        # filler people, every one of them a real (if unqueried) 0.
        immich = _FakeImmich(persons=[subject, *others], co_occurrence={})

        assert PhotosTogetherQuestion().can_generate(immich, frozenset()) is False

    def test_can_generate_is_false_when_the_top_co_occurrence_is_tied(self):
        subject = _person("Subject")
        a, b, c, d = (_person(f"P{i}") for i in range(4))
        immich = _FakeImmich(
            persons=[subject, a, b, c, d],
            co_occurrence={subject.id: [(a.id, a.name, 5), (b.id, b.name, 5), (c.id, c.name, 2), (d.id, d.name, 1)]},
        )

        assert PhotosTogetherQuestion().can_generate(immich, frozenset()) is False

    def test_can_generate_is_true_once_a_unique_positive_max_exists(self):
        subject = _person("Subject")
        a, b, c, d = (_person(f"P{i}") for i in range(4))
        immich = _FakeImmich(
            persons=[subject, a, b, c, d],
            co_occurrence={subject.id: [(a.id, a.name, 9), (b.id, b.name, 5), (c.id, c.name, 2), (d.id, d.name, 1)]},
        )

        assert PhotosTogetherQuestion().can_generate(immich, frozenset()) is True
        question = PhotosTogetherQuestion().generate(immich, frozenset())
        assert question.alternatives[question.correct_index]["person_id"] == str(a.id)

    def test_candidates_are_a_random_four_not_always_the_top_four(self):
        # Confirmed by the owner: the correct answer shouldn't always be whoever has the single
        # highest co-occurrence with the subject - 8 people with strictly distinct counts (so
        # every possible group of 4 still has a valid unique max) makes it easy to tell whether
        # the same literal top-4 set is being reused every time.
        subject = _person("Subject")
        people = [_person(f"P{i}") for i in range(8)]
        co_occurrence = [(p.id, p.name, 8 - i) for i, p in enumerate(people)]
        immich = _FakeImmich(persons=[subject, *people], co_occurrence={subject.id: co_occurrence})
        top_four_ids = frozenset(p.id for p in people[:4])

        seen_candidate_sets = set()
        for _ in range(50):
            question = PhotosTogetherQuestion().generate(immich, frozenset())
            seen_candidate_sets.add(frozenset(UUID(alt["person_id"]) for alt in question.alternatives))

        assert len(seen_candidate_sets) > 1
        assert seen_candidate_sets != {top_four_ids}


class TestPhotosFirstAssetYearQuestionAgainstRealData:
    def test_can_generate_is_true_with_the_dev_library(self, immich_service):
        assert PhotosFirstAssetYearQuestion().can_generate(immich_service, frozenset())

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question = PhotosFirstAssetYearQuestion().generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == FIRST_ASSET_YEAR_KIND
        assert len(question.alternatives) == 4
        assert len(set(question.alternatives)) == 4
        assert 0 <= question.correct_index < 4
        assert question.media.kind == "person_thumbnail"

    def test_the_correct_alternative_is_the_subjects_real_first_asset_year(self, immich_service):
        question = PhotosFirstAssetYearQuestion().generate(immich_service, frozenset())
        first_date = immich_service.get_person_first_asset_date(question.subject_id)
        assert question.alternatives[question.correct_index] == first_date.year


class TestPhotosFirstAssetYearQuestionEdgeCases:
    def test_can_generate_is_false_when_the_year_range_is_too_narrow(self):
        people = [_person(f"P{i}") for i in range(4)]
        # Every person's first photo is from the same year - no room for 3 distinct distractors.
        immich = _FakeImmich(persons=people, first_asset_dates={p.id: date(2020, 1, 1) for p in people})

        assert PhotosFirstAssetYearQuestion().can_generate(immich, frozenset()) is False

    def test_can_generate_is_true_once_the_range_is_wide_enough(self):
        people = [_person(f"P{i}") for i in range(4)]
        dates = [date(2018, 1, 1), date(2019, 1, 1), date(2020, 1, 1), date(2021, 1, 1)]
        immich = _FakeImmich(persons=people, first_asset_dates=dict(zip((p.id for p in people), dates, strict=True)))

        assert PhotosFirstAssetYearQuestion().can_generate(immich, frozenset()) is True
