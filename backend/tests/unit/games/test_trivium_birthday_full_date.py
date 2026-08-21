"""Integration tests against the real dev Immich Postgres (see tests/conftest.py) - mirrors
test_trivium_birthday_year.py's structure."""

from datetime import date

from games.trivium.questions.base import GeneratedQuestion
from games.trivium.questions.birthday_full_date import KIND, BirthdayFullDateQuestion


class TestBirthdayFullDateQuestionAgainstRealData:
    def test_can_generate_is_true_with_the_dev_library(self, immich_service):
        assert BirthdayFullDateQuestion().can_generate(immich_service, frozenset())

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question_type = BirthdayFullDateQuestion()
        question = question_type.generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == KIND
        assert len(question.alternatives) == 4
        assert len(set(question.alternatives)) == 4
        assert 0 <= question.correct_index < 4
        assert question.media.kind == "person_thumbnail"
        for alt in question.alternatives:
            date.fromisoformat(alt)  # every alternative is a real, parseable ISO date

    def test_the_correct_alternative_is_the_subjects_real_birth_date(self, immich_service):
        question_type = BirthdayFullDateQuestion()
        question = question_type.generate(immich_service, frozenset())

        [subject] = immich_service.get_persons(
            named_only=True, with_birthdate=True, ids=frozenset({question.subject_id})
        )
        assert question.alternatives[question.correct_index] == subject.birth_date.isoformat()

    def test_distractor_years_stay_within_one_year_of_the_subjects_real_birth_year(self, immich_service):
        question_type = BirthdayFullDateQuestion()
        for _ in range(50):
            question = question_type.generate(immich_service, frozenset())
            [subject] = immich_service.get_persons(
                named_only=True, with_birthdate=True, ids=frozenset({question.subject_id})
            )
            correct_year = subject.birth_date.year
            for alt in question.alternatives:
                assert correct_year - 1 <= date.fromisoformat(alt).year <= correct_year + 1

    def test_excluding_every_birthdated_person_makes_it_ungeneratable(self, immich_service):
        question_type = BirthdayFullDateQuestion()
        everyone = immich_service.get_persons(named_only=True, with_birthdate=True, limit=10_000)
        all_ids = frozenset(p.id for p in everyone)

        assert question_type.can_generate(immich_service, all_ids) is False
