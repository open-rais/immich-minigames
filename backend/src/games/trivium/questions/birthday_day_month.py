"""birthday_day_month question type - "when is {person}'s birthday" (day + month, no year), with
distractors generated the same way birthday_year's are: noise on the real date rather than other
people's real birthdays."""

import random
from uuid import UUID

from games.trivium.questions._shared import pick_day_month_distractors
from games.trivium.questions.base import GeneratedQuestion, MediaSpec
from services.immich import ContentQueries

KIND = "birthday_day_month"


class BirthdayDayMonthQuestion:
    def can_generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> bool:
        # Unlike birthday_year, there's no library-range check needed: every day-of-year is an
        # equally plausible birthday, so the only real requirement is having a subject at all.
        return bool(
            immich_service.get_persons(named_only=True, with_birthdate=True, limit=1, exclude_ids=exclude_subject_ids)
        )

    def generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> GeneratedQuestion:
        [subject] = immich_service.get_persons(
            named_only=True, with_birthdate=True, randomize=True, limit=1, exclude_ids=exclude_subject_ids
        )
        # with_birthdate=True already filters out anyone with no birth_date, so it's never None here.
        correct_date = subject.birth_date

        distractors = pick_day_month_distractors(correct_date)
        alternatives: list[dict[str, int]] = [{"month": d.month, "day": d.day} for d in [*distractors, correct_date]]
        random.shuffle(alternatives)
        correct_value = {"month": correct_date.month, "day": correct_date.day}

        return GeneratedQuestion(
            question_kind=KIND,
            subject_id=subject.id,
            params={"person_id": str(subject.id), "person_name": subject.name},
            alternatives=alternatives,
            correct_index=alternatives.index(correct_value),
            media=MediaSpec(kind="person_thumbnail", person_id=subject.id),
        )
