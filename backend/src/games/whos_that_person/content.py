"""The single point of variation between a normal Who'sThatPerson game and a daily one - live
Immich queries (LiveContent below) vs. a frozen daily spec (games/whos_that_person/daily.py's
ScriptedContent). games/whos_that_person/game.py's WhosThatPersonGame never knows which."""

import random
from typing import Protocol
from uuid import UUID

from games.whos_that_person.round import HiddenFace
from services.immich import ContentQueries


class WhosThatPersonContent(Protocol):
    """The single point of variation between a normal Who'sThatPerson game and a daily one - live
    Immich queries (LiveContent below) vs. a frozen daily spec (games/whos_that_person/daily.py's
    ScriptedContent). The game engine below never knows which.

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
        faces = self._immich_service.get_random_asset_with_named_faces(exclude_asset_ids=exclude_asset_ids)
        if not faces:
            return None
        # Hide every named face if there are max_faces or fewer, otherwise a *random* number of
        # them between 1 and max_faces (not always exactly max_faces, so a photo with plenty of
        # named people doesn't deterministically always hide the maximum).
        if len(faces) > max_faces:
            faces = random.sample(faces, random.randint(1, max_faces))
        return faces[0].asset_id, [HiddenFace.of(f) for f in faces]

    def has_more(self, max_faces: int, exclude_asset_ids: frozenset[UUID]) -> bool:
        # A real existence check (not pick_round() discarded, unlike this used to be) - see
        # services/immich/faces.py's has_named_faces_asset: a plain LIMIT-1 query over the same
        # eligibility join, without the id-pivot sample or the second (per-asset faces) query
        # pick_round() itself needs. Same pattern games/timeline/content.py's LiveContent.has_more
        # already uses.
        return self._immich_service.has_named_faces_asset(exclude_asset_ids=exclude_asset_ids)
