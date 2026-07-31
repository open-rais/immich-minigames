"""personAssets mode - see games/more_or_less/content.py's CandidateProvider."""

from uuid import UUID

from games.more_or_less.content import CandidateProvider
from games.more_or_less.round import EntitySnapshot
from services.immich import ContentQueries


class PersonAssetsProvider(CandidateProvider):
    def __init__(self, immich_service: ContentQueries) -> None:
        self._immich_service = immich_service

    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        people = self._immich_service.get_persons(named_only=True, randomize=True, limit=limit, exclude_ids=exclude_ids)
        return [EntitySnapshot(id=p.id, name=p.name, value=p.asset_count) for p in people]

    def any_exist(self) -> bool:
        return bool(self._immich_service.get_persons(named_only=True, limit=1))
