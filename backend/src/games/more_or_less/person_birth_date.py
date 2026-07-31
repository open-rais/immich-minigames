"""personBirthDate mode - see games/more_or_less/content.py's CandidateProvider.

`value` is the person's birth date as an ISO-8601 string (`date.isoformat()`) - lexicographic
ordering of "YYYY-MM-DD" strings matches chronological order exactly, so the generic
`candidate.value > reference.value` comparison in games/more_or_less/round.py's
MoreOrLessRound.calculate_score already means "born after" for "more" and "born before" for
"less" with no extra code."""

from uuid import UUID

from games.more_or_less.content import CandidateProvider
from games.more_or_less.round import EntitySnapshot
from services.immich import ContentQueries


class PersonBirthDateProvider(CandidateProvider):
    def __init__(self, immich_service: ContentQueries) -> None:
        self._immich_service = immich_service

    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        people = self._immich_service.get_persons(
            named_only=True, with_birthdate=True, randomize=True, limit=limit, exclude_ids=exclude_ids
        )
        # with_birthdate=True already filters out anyone with no birth_date, so it's never None here.
        return [EntitySnapshot(id=p.id, name=p.name, value=p.birth_date.isoformat()) for p in people]

    def any_exist(self) -> bool:
        return bool(self._immich_service.get_persons(named_only=True, with_birthdate=True, limit=1))
