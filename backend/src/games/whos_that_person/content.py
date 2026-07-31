"""The single point of variation between a normal Who'sThatPerson game and a daily one
(roadmap #G) - live Immich queries (LiveContent below) vs. a frozen daily spec
(games/whos_that_person/daily.py's ScriptedContent). games/whos_that_person/game.py's
WhosThatPersonGame never knows which."""

from typing import Protocol
from uuid import UUID

from games.whos_that_person.round import HiddenFace
from services.immich import ContentQueries


class WhosThatPersonContent(Protocol):
    """The single point of variation between a normal Who'sThatPerson game and a daily one
    (roadmap #G) - live Immich queries (LiveContent below) vs. a frozen daily spec
    (games/whos_that_person/daily.py's ScriptedContent). The game engine below never knows which.

    `has_more` and `pick_round` are deliberately separate methods, not "call pick_round and discard
    the result" - LiveContent's query is idempotent to repeat, but ScriptedContent's pick_round
    advances an internal index on every successful call, so has_next_round() checking availability
    by calling (and discarding) pick_round would silently skip a round."""

    def has_more(self, max_faces: int, exclude_asset_ids: frozenset[UUID]) -> bool:
        """Whether another round's worth of content is available, without actually picking it."""
        ...

    def pick_round(self, max_faces: int, exclude_asset_ids: frozenset[UUID]) -> tuple[UUID, list[HiddenFace]] | None:
        """The next round's photo + which of its named faces to hide - None when no eligible photo
        is left."""
        ...


class LiveContent:
    """Normal-play WhosThatPersonContent - samples an eligible photo straight from Immich."""

    def __init__(self, immich_service: ContentQueries) -> None:
        self._immich_service = immich_service

    def pick_round(self, max_faces: int, exclude_asset_ids: frozenset[UUID]) -> tuple[UUID, list[HiddenFace]] | None:
        faces = self._immich_service.get_random_asset_with_named_faces(
            max_faces=max_faces, exclude_asset_ids=exclude_asset_ids
        )
        if not faces:
            return None
        return faces[0].asset_id, [HiddenFace.of(f) for f in faces]

    def has_more(self, max_faces: int, exclude_asset_ids: frozenset[UUID]) -> bool:
        # Cheap-ish existence check, discarded - create_next_round() samples again, same
        # double-sample pattern MoreOrLessGame/GeoguessrGame already use. Safe to repeat here since
        # a live query has no side effect (unlike ScriptedContent.has_more).
        return self.pick_round(max_faces, exclude_asset_ids) is not None
