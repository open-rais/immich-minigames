"""albumAssets mode - see games/more_or_less/game.py's CandidateProvider."""

from uuid import UUID

from games.more_or_less.game import CandidateProvider, EntitySnapshot
from services.immich_service import ImmichService


class AlbumAssetsProvider(CandidateProvider):
    def __init__(self, immich_service: ImmichService) -> None:
        self._immich_service = immich_service

    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        albums = self._immich_service.get_albums(randomize=True, limit=limit, exclude_ids=exclude_ids)
        return [EntitySnapshot(id=a.id, name=a.name, value=a.asset_count) for a in albums]

    def any_exist(self) -> bool:
        return bool(self._immich_service.get_albums(limit=1))
