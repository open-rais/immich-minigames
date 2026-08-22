"""birthday_full_date question type - "what day was {person} born" (the full date). Distractors
vary day/month as widely as birthday_day_month's, but keep the year within +/-1 of the real one -
see games/trivium/questions/_shared.py's module docstring for why the noise magnitude shrinks as a
question gets more specific."""

import random
from uuid import UUID

from games.trivium.questions._shared import pick_full_date_distractors
from games.trivium.questions.base import GeneratedQuestion, MediaSpec
from services.immich import ContentQueries

KIND = "birthday_full_date"


class BirthdayFullDateQuestion:
    def generate(
        self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]
    ) -> GeneratedQuestion | None:
        # No library-range check needed (unlike birthday_year/photos_first_asset_year): the +/-1
        # year window is self-contained around whichever subject gets picked, always wide enough
        # (~2-3 years of days) for 3 distinct distractors regardless of what the library contains.
        candidates = immich_service.get_persons(
            named_only=True, with_birthdate=True, randomize=True, limit=1, exclude_ids=exclude_subject_ids
        )
        if not candidates:
            return None
        subject = candidates[0]
        # with_birthdate=True already filters out anyone with no birth_date, so it's never None here.
        correct_date = subject.birth_date

        distractors = pick_full_date_distractors(correct_date)

        # ISO date strings, not a pre-formatted sentence - the frontend formats per the active
        # locale (same "structured date" convention as every other date this app ever sends).
        alternatives: list[str] = [d.isoformat() for d in [*distractors, correct_date]]
        random.shuffle(alternatives)

        return GeneratedQuestion(
            question_kind=KIND,
            subject_id=subject.id,
            params={"person_id": str(subject.id), "person_name": subject.name},
            alternatives=alternatives,
            correct_index=alternatives.index(correct_date.isoformat()),
            media=MediaSpec(kind="person_thumbnail", person_id=subject.id),
        )
