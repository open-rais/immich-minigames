"""Integration tests against the real dev Immich Postgres (see tests/conftest.py) - BirthYearQuestion
needs real named+birthdated people to pick a subject from and a real birth-year spread to clamp
distractor noise against, which a fake ContentQueries double would just be reimplementing the
query logic to fake."""

from games.trivium.questions.base import GeneratedQuestion
from games.trivium.questions.birthday_year import KIND, BirthYearQuestion, _pick_distractor_years


class TestPickDistractorYears:
    """Pure - no DB needed."""

    def test_always_returns_three_distinct_years_other_than_correct(self):
        for _ in range(500):
            distractors = _pick_distractor_years(correct_year=2000, min_year=1990, max_year=2010)
            assert len(distractors) == 3
            assert len(set(distractors)) == 3
            assert 2000 not in distractors
            assert all(1990 <= year <= 2010 for year in distractors)

    def test_works_at_the_minimum_generatable_span(self):
        # can_generate() only allows this type through when max_year - min_year >= 3, i.e. exactly
        # 4 distinct integer years total - the tightest case that must still terminate.
        for _ in range(200):
            distractors = _pick_distractor_years(correct_year=2000, min_year=2000, max_year=2003)
            assert sorted({*distractors, 2000}) == [2000, 2001, 2002, 2003]

    def test_works_when_correct_year_sits_at_the_edge_of_the_range(self):
        for _ in range(200):
            distractors = _pick_distractor_years(correct_year=1990, min_year=1990, max_year=2010)
            assert len(set(distractors)) == 3
            assert 1990 not in distractors


class TestBirthYearQuestionAgainstRealData:
    def test_can_generate_is_true_with_the_dev_library(self, immich_service):
        # The dev stack has several named people with a birthDate spanning decades (see
        # docs/ARCHITECTURE/IMMICH.md) - if this ever goes False, the fixture data changed enough
        # to also break every other test below.
        assert BirthYearQuestion().can_generate(immich_service, frozenset())

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question_type = BirthYearQuestion()
        question = question_type.generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == KIND
        assert len(question.alternatives) == 4
        assert len(set(question.alternatives)) == 4
        assert 0 <= question.correct_index < 4
        assert question.params["person_id"] == str(question.subject_id)
        assert isinstance(question.params["person_name"], str) and question.params["person_name"]
        assert question.media.kind == "person_thumbnail"
        assert question.media.person_id == question.subject_id

    def test_the_correct_alternative_is_the_subjects_real_birth_year(self, immich_service):
        question_type = BirthYearQuestion()
        question = question_type.generate(immich_service, frozenset())

        [subject] = immich_service.get_persons(
            named_only=True, with_birthdate=True, ids=frozenset({question.subject_id})
        )
        assert question.alternatives[question.correct_index] == subject.birth_date.year

    def test_distractors_never_collide_with_the_correct_answer(self, immich_service):
        question_type = BirthYearQuestion()
        for _ in range(50):
            question = question_type.generate(immich_service, frozenset())
            assert len(set(question.alternatives)) == 4

    def test_excluding_every_birthdated_person_makes_it_ungeneratable(self, immich_service):
        question_type = BirthYearQuestion()
        everyone = immich_service.get_persons(named_only=True, with_birthdate=True, limit=10_000)
        all_ids = frozenset(p.id for p in everyone)

        assert question_type.can_generate(immich_service, all_ids) is False

    def test_a_given_subject_is_never_reoffered_once_excluded(self, immich_service):
        question_type = BirthYearQuestion()
        question = question_type.generate(immich_service, frozenset())
        excluded = frozenset({question.subject_id})

        assert question_type.can_generate(immich_service, excluded)
        for _ in range(20):
            next_question = question_type.generate(immich_service, excluded)
            assert next_question.subject_id != question.subject_id
