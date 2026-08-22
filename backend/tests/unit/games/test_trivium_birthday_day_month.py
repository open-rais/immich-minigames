"""Integration tests against the real dev Immich Postgres (see tests/conftest.py) - mirrors
test_trivium_birthday_year.py's structure."""

from games.trivium.questions.base import GeneratedQuestion
from games.trivium.questions.birthday_day_month import KIND, BirthdayDayMonthQuestion


class TestBirthdayDayMonthQuestionAgainstRealData:
    def test_generate_succeeds_with_the_dev_library(self, immich_service):
        assert BirthdayDayMonthQuestion().generate(immich_service, frozenset()) is not None

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question_type = BirthdayDayMonthQuestion()
        question = question_type.generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == KIND
        assert len(question.alternatives) == 4
        assert 0 <= question.correct_index < 4
        assert question.params["person_id"] == str(question.subject_id)
        assert question.media.kind == "person_thumbnail"
        assert question.media.person_id == question.subject_id
        for alt in question.alternatives:
            assert set(alt.keys()) == {"month", "day"}

    def test_the_correct_alternative_is_the_subjects_real_birthday(self, immich_service):
        question_type = BirthdayDayMonthQuestion()
        question = question_type.generate(immich_service, frozenset())

        [subject] = immich_service.get_persons(
            named_only=True, with_birthdate=True, ids=frozenset({question.subject_id})
        )
        correct = question.alternatives[question.correct_index]
        assert correct == {"month": subject.birth_date.month, "day": subject.birth_date.day}

    def test_distractors_never_collide_with_the_correct_answer_or_each_other(self, immich_service):
        question_type = BirthdayDayMonthQuestion()
        for _ in range(50):
            question = question_type.generate(immich_service, frozenset())
            keys = [(a["month"], a["day"]) for a in question.alternatives]
            assert len(set(keys)) == 4

    def test_excluding_every_birthdated_person_makes_it_ungeneratable(self, immich_service):
        question_type = BirthdayDayMonthQuestion()
        everyone = immich_service.get_persons(named_only=True, with_birthdate=True, limit=10_000)
        all_ids = frozenset(p.id for p in everyone)

        assert question_type.generate(immich_service, all_ids) is None
