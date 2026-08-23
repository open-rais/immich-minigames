"""Pure unit tests (no DB) for Trivium's daily support
(games/trivium/daily.py::ScriptedQuestionType/exclusion_ids/game_kwargs/build_spec) and its
PooledContentQueries wrapper (games/trivium/pooled_content.py). Hand-constructed questions/content,
so none of this needs the immich_service/db_session fixtures - see
tests/unit/services/test_daily_challenge_service.py's TestSpecShapePerGame/TestExclusionWindow for
the integration-level coverage (build_spec's actual shape against the real dev Immich instance, two
players/days sharing or excluding content) that does need those."""

import random
from collections import Counter
from datetime import date
from uuid import UUID, uuid4

from domain.asset import Asset
from domain.person import Person
from games.trivium.daily import ScriptedQuestionType, build_spec, exclusion_ids, game_kwargs
from games.trivium.pooled_content import PooledContentQueries
from games.trivium.questions.base import GeneratedQuestion, MediaSpec


def _question(**overrides: object) -> GeneratedQuestion:
    defaults: dict[str, object] = {
        "question_kind": "birthday_year",
        "subject_id": uuid4(),
        "params": {"person_id": str(uuid4()), "person_name": "Someone"},
        "alternatives": [1990, 1991, 1992, 1993],
        "correct_index": 0,
        "media": MediaSpec(),
    }
    return GeneratedQuestion(**{**defaults, **overrides})  # type: ignore[arg-type]


class TestScriptedQuestionType:
    def test_generate_replays_questions_in_order(self):
        questions = [_question(question_kind="birthday_year"), _question(question_kind="photos_total_assets")]
        scripted = ScriptedQuestionType(questions, next_index=0)

        first = scripted.generate(immich_service=None, exclude_subject_ids=frozenset())
        second = scripted.generate(immich_service=None, exclude_subject_ids=frozenset())

        assert first is questions[0]
        assert second is questions[1]

    def test_ignores_exclude_subject_ids(self):
        # Same "already built repeat-free at generation time" convention as every other game's
        # scripted replay - a real subject exclusion set here must not filter anything out.
        question = _question()
        scripted = ScriptedQuestionType([question], next_index=0)

        result = scripted.generate(immich_service=None, exclude_subject_ids=frozenset({question.subject_id}))

        assert result is question

    def test_generate_returns_none_once_exhausted(self):
        scripted = ScriptedQuestionType([_question()], next_index=1)

        assert scripted.generate(immich_service=None, exclude_subject_ids=frozenset()) is None

    def test_resuming_mid_chain_continues_from_the_right_index(self):
        # Mirrors games/trivium/daily.py's game_kwargs after 2 rounds already exist:
        # next_index = rounds_played (2), no +1 offset (unlike MoreOrLess/Timeline's chain).
        questions = [_question(), _question(), _question(question_kind="location_country")]
        scripted = ScriptedQuestionType(questions, next_index=2)

        result = scripted.generate(immich_service=None, exclude_subject_ids=frozenset())

        assert result is questions[2]


class TestExclusionIds:
    def test_returns_every_subject_in_the_spec(self):
        questions = [_question(), _question(), _question()]
        spec = {
            "questions": [
                {
                    "question_kind": q.question_kind,
                    "subject_id": str(q.subject_id),
                    "params": q.params,
                    "alternatives": q.alternatives,
                    "correct_index": q.correct_index,
                    "media": {"kind": q.media.kind},
                }
                for q in questions
            ]
        }

        ids = exclusion_ids(spec)

        assert ids == {q.subject_id for q in questions}


class TestGameKwargs:
    def test_round_trips_a_question_through_the_payload_shape(self):
        original = _question(
            question_kind="mixed_name_to_face",
            alternatives=[{"person_id": str(uuid4()), "person_name": "A"}],
            media=MediaSpec(kind="person_thumbnail", person_id=uuid4()),
        )
        spec = {
            "questions": [
                {
                    "question_kind": original.question_kind,
                    "subject_id": str(original.subject_id),
                    "params": original.params,
                    "alternatives": original.alternatives,
                    "correct_index": original.correct_index,
                    "media": {"kind": original.media.kind, "person_id": str(original.media.person_id)},
                }
            ]
        }

        kwargs = game_kwargs(
            "mixed",
            spec,
            {},
            rounds_played=0,
            immich_service=None,
            ml_service=None,  # type: ignore[arg-type]
        )
        [question_type] = kwargs["question_types"]
        replayed = question_type.generate(immich_service=None, exclude_subject_ids=frozenset())

        assert replayed.question_kind == original.question_kind
        assert replayed.subject_id == original.subject_id
        assert replayed.alternatives == original.alternatives
        assert replayed.media.kind == "person_thumbnail"
        assert replayed.media.person_id == original.media.person_id
        assert kwargs["mode"] == "mixed"


def _person(index: int, *, asset_count: int, birth_date: date | None = None) -> Person:
    return Person(id=uuid4(), name=f"Person {index}", birth_date=birth_date, asset_count=asset_count)


def _asset(index: int, *, city: str | None = None, country: str | None = None) -> Asset:
    return Asset(
        id=uuid4(),
        type="IMAGE",
        file_created_at=date(2020, 1, 1),  # type: ignore[arg-type]
        local_date=date(2020, 1, 1),
        original_file_name=f"asset-{index}.jpg",
        width=100,
        height=100,
        is_favorite=False,
        latitude=1.0 if city or country else None,
        longitude=1.0 if city or country else None,
        city=city,
        state=None,
        country=country,
    )


class _FakeContentQueries:
    """A tiny in-memory ContentQueries double, filtering the same knobs
    services/immich/persons.py's get_persons and services/immich/assets.py's get_assets support -
    counts real calls per method, the PooledContentQueries equivalent of
    test_more_or_less_daily.py's _FakePool.calls (one counter per method here, since
    PooledContentQueries wraps several)."""

    def __init__(
        self,
        persons: list[Person] | None = None,
        assets: list[Asset] | None = None,
        co_occurring: dict[UUID, list[tuple[UUID, str, int]]] | None = None,
        first_asset_dates: dict[UUID, date] | None = None,
    ) -> None:
        self.persons = persons or []
        self.assets = assets or []
        self._co_occurring = co_occurring or {}
        self._first_asset_dates = first_asset_dates or {}
        self.calls: Counter[str] = Counter()

    def get_persons(
        self,
        *,
        named_only: bool = True,
        with_birthdate: bool | None = None,
        min_asset_count: int | None = None,
        name_query: str | None = None,
        ids: frozenset[UUID] | None = None,
        randomize: bool = False,
        asset_count_weight: float | None = None,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Person]:
        self.calls["get_persons"] += 1
        pool = self.persons
        if named_only:
            pool = [p for p in pool if p.name]
        if with_birthdate is True:
            pool = [p for p in pool if p.birth_date is not None]
        elif with_birthdate is False:
            pool = [p for p in pool if p.birth_date is None]
        if name_query:
            pool = [p for p in pool if name_query.lower() in p.name.lower()]
        if ids is not None:
            pool = [p for p in pool if p.id in ids]
        if exclude_ids:
            pool = [p for p in pool if p.id not in exclude_ids]
        if min_asset_count is not None:
            pool = [p for p in pool if p.asset_count >= min_asset_count]
        pool = list(pool)
        if randomize:
            random.shuffle(pool)
        else:
            pool = sorted(pool, key=lambda p: p.name)
        return pool[:limit]

    def get_assets(
        self,
        *,
        media_type: str = "any",
        with_location: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        local_date: date | None = None,
        local_month: int | None = None,
        near_km: tuple[float, float, float] | None = None,
        randomize: bool = False,
        limit: int = 1,
        ids: frozenset[UUID] | None = None,
        exclude_ids: frozenset[UUID] = frozenset(),
    ) -> list[Asset]:
        self.calls["get_assets"] += 1
        pool = self.assets
        if media_type == "photo":
            pool = [a for a in pool if a.type == "IMAGE"]
        elif media_type == "video":
            pool = [a for a in pool if a.type == "VIDEO"]
        if with_location is True:
            pool = [a for a in pool if a.latitude is not None]
        elif with_location is False:
            pool = [a for a in pool if a.latitude is None]
        if ids is not None:
            pool = [a for a in pool if a.id in ids]
        if exclude_ids:
            pool = [a for a in pool if a.id not in exclude_ids]
        pool = list(pool)
        if randomize:
            random.shuffle(pool)
        return pool[:limit]

    def get_distinct_locations(self, field: str) -> list[str]:
        self.calls["get_distinct_locations"] += 1
        values = (a.city if field == "city" else a.country for a in self.assets)
        return sorted({v for v in values if v is not None})

    def get_top_co_occurring_persons(
        self, person_id: UUID, *, limit: int = 3, exclude_ids: frozenset[UUID] = frozenset()
    ) -> list[tuple[UUID, str, int]]:
        self.calls["get_top_co_occurring_persons"] += 1
        candidates = [c for c in self._co_occurring.get(person_id, []) if c[0] not in exclude_ids]
        return sorted(candidates, key=lambda c: -c[2])[:limit]

    def get_person_first_asset_date(self, person_id: UUID) -> date | None:
        self.calls["get_person_first_asset_date"] += 1
        return self._first_asset_dates.get(person_id)


def _photos_mode_fake(num_persons: int = 12) -> _FakeContentQueries:
    """Enough synthetic persons for every photos-mode question type
    (games/trivium/questions/photos_total_assets.py, photos_together.py,
    photos_first_asset_year.py) to reliably generate() on the first attempt: distinct asset_counts
    (a random group of 4 always has a unique max), a full ring of distinct-count co-occurrence data
    per person (so photos_together never needs its filler/retry paths), and first-asset years
    spread across `num_persons` distinct years (comfortably over pick_distractor_years' >= 4
    requirement)."""
    persons = [_person(i, asset_count=100 + i) for i in range(num_persons)]
    co_occurring = {
        p.id: [
            (persons[(i + offset) % num_persons].id, persons[(i + offset) % num_persons].name, offset)
            for offset in (1, 2, 3, 4)
        ]
        for i, p in enumerate(persons)
    }
    first_asset_dates = {p.id: date(2010 + i, 6, 15) for i, p in enumerate(persons)}
    return _FakeContentQueries(persons=persons, co_occurring=co_occurring, first_asset_dates=first_asset_dates)


class TestPooledContentQueriesGetPersons:
    def test_repeated_calls_with_the_same_hard_filters_hit_the_inner_service_once(self):
        fake = _FakeContentQueries(persons=[_person(i, asset_count=i) for i in range(10)])
        pooled = PooledContentQueries(fake)

        for _ in range(5):
            pooled.get_persons(named_only=True, limit=3, exclude_ids=frozenset())

        assert fake.calls["get_persons"] == 1

    def test_exclude_ids_are_filtered_in_memory_not_re_queried(self):
        persons = [_person(i, asset_count=i) for i in range(5)]
        fake = _FakeContentQueries(persons=persons)
        pooled = PooledContentQueries(fake)

        excluded = frozenset({persons[0].id, persons[1].id})
        result = pooled.get_persons(named_only=True, limit=10, exclude_ids=excluded)

        assert fake.calls["get_persons"] == 1
        assert {p.id for p in result} == {p.id for p in persons[2:]}

    def test_randomize_does_not_always_serve_the_same_order(self):
        persons = [_person(i, asset_count=i) for i in range(20)]
        fake = _FakeContentQueries(persons=persons)
        pooled = PooledContentQueries(fake)

        samples = [
            tuple(p.id for p in pooled.get_persons(named_only=True, randomize=True, limit=5))
            for _ in range(10)
        ]

        assert fake.calls["get_persons"] == 1  # one pool build, ten in-memory samples
        assert len(set(samples)) > 1

    def test_different_hard_filter_combos_get_separate_pools(self):
        persons = [_person(i, asset_count=i, birth_date=date(2000, 1, 1) if i % 2 == 0 else None) for i in range(10)]
        fake = _FakeContentQueries(persons=persons)
        pooled = PooledContentQueries(fake)

        pooled.get_persons(named_only=True, with_birthdate=True, limit=10)
        pooled.get_persons(named_only=True, with_birthdate=False, limit=10)
        pooled.get_persons(named_only=True, with_birthdate=True, limit=10)

        assert fake.calls["get_persons"] == 2  # one pool per distinct (named_only, with_birthdate)

    def test_ids_name_query_min_asset_count_and_asset_count_weight_always_bypass_the_pool(self):
        persons = [_person(i, asset_count=i) for i in range(5)]
        fake = _FakeContentQueries(persons=persons)
        pooled = PooledContentQueries(fake)

        pooled.get_persons(ids=frozenset({persons[0].id}), limit=1)
        pooled.get_persons(ids=frozenset({persons[0].id}), limit=1)
        pooled.get_persons(name_query="Person", limit=5)
        pooled.get_persons(min_asset_count=1, limit=5)
        pooled.get_persons(randomize=True, asset_count_weight=1.0, limit=5)

        assert fake.calls["get_persons"] == 5  # never cached


class TestPooledContentQueriesGetAssets:
    def test_repeated_calls_with_the_same_hard_filters_hit_the_inner_service_once(self):
        assets = [_asset(i, city="Santiago", country="Chile") for i in range(10)]
        fake = _FakeContentQueries(assets=assets)
        pooled = PooledContentQueries(fake)

        for _ in range(4):
            pooled.get_assets(media_type="photo", with_location=True, limit=3, randomize=True)

        assert fake.calls["get_assets"] == 1

    def test_ids_lookup_always_bypasses_the_pool(self):
        assets = [_asset(i, city="Santiago", country="Chile") for i in range(5)]
        fake = _FakeContentQueries(assets=assets)
        pooled = PooledContentQueries(fake)

        pooled.get_assets(ids=frozenset({assets[0].id}), limit=1)
        pooled.get_assets(ids=frozenset({assets[1].id}), limit=1)

        assert fake.calls["get_assets"] == 2


class TestPooledContentQueriesMemoizedLookups:
    def test_get_top_co_occurring_persons_is_memoized_by_subject_and_limit(self):
        subject_id = uuid4()
        other_id = uuid4()
        fake = _FakeContentQueries(co_occurring={subject_id: [(other_id, "Other", 3)]})
        pooled = PooledContentQueries(fake)

        for _ in range(5):
            pooled.get_top_co_occurring_persons(subject_id, limit=20)
        pooled.get_top_co_occurring_persons(subject_id, limit=5)  # different limit -> fresh call

        assert fake.calls["get_top_co_occurring_persons"] == 2

    def test_non_empty_exclude_ids_always_bypasses_the_cache(self):
        subject_id = uuid4()
        fake = _FakeContentQueries()
        pooled = PooledContentQueries(fake)

        pooled.get_top_co_occurring_persons(subject_id, limit=20, exclude_ids=frozenset({uuid4()}))
        pooled.get_top_co_occurring_persons(subject_id, limit=20, exclude_ids=frozenset({uuid4()}))

        assert fake.calls["get_top_co_occurring_persons"] == 2

    def test_get_person_first_asset_date_is_memoized_per_person(self):
        person_id = uuid4()
        fake = _FakeContentQueries(first_asset_dates={person_id: date(2020, 1, 1)})
        pooled = PooledContentQueries(fake)

        for _ in range(5):
            pooled.get_person_first_asset_date(person_id)

        assert fake.calls["get_person_first_asset_date"] == 1

    def test_get_distinct_locations_is_memoized_per_field(self):
        fake = _FakeContentQueries(assets=[_asset(0, city="Santiago", country="Chile")])
        pooled = PooledContentQueries(fake)

        for _ in range(5):
            pooled.get_distinct_locations("city")
        pooled.get_distinct_locations("country")  # different field -> fresh call

        assert fake.calls["get_distinct_locations"] == 2


class TestBuildSpecQueryCeiling:
    """Without pooling, every one of these calls scales with chain_length (each round's
    generate() re-queries from scratch) - with PooledContentQueries wired into build_spec, they're
    bounded by the fake's own content size instead, regardless of how many rounds get
    generated."""

    def test_photos_mode_query_counts_stay_bounded_by_content_not_rounds(self):
        num_persons = 12
        fake = _photos_mode_fake(num_persons)

        spec = build_spec("photos", fake, {"chain_length": 30})

        assert len(spec["questions"]) == 30
        # get_persons: every photos-mode call uses the same (named_only=True, with_birthdate=None)
        # combo, so one pool build serves the whole 30-round chain.
        assert fake.calls["get_persons"] <= 2
        # get_top_co_occurring_persons/get_person_first_asset_date: memoized per person - at most
        # one real call per distinct person regardless of how many rounds retry them.
        assert fake.calls["get_top_co_occurring_persons"] <= num_persons
        assert fake.calls["get_person_first_asset_date"] <= num_persons

    def test_two_generations_do_not_produce_the_same_chain(self):
        first = build_spec("photos", _photos_mode_fake(), {"chain_length": 10})
        second = build_spec("photos", _photos_mode_fake(), {"chain_length": 10})

        assert first["questions"] != second["questions"]
