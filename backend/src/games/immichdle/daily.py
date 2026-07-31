"""Immichdle's DailySupport implementation (games/daily.py's contract) - shared by both modes,
dispatching build_spec/game_kwargs by `mode` to persondle.py's/albumdle.py's own functions
(mirrors games/more_or_less/daily.py's per-mode dispatch, which also keeps one shared daily.py
rather than splitting it per mode - only the mode-specific *content* logic lives in the per-mode
files). `exclusion_ids` needs no such dispatch at all: both PersonSnapshot.to_dict() and
AlbumSnapshot.to_dict() put the target's id at spec["target"]["id"], so one implementation covers
both modes."""

from typing import Any
from uuid import UUID

from games.immichdle import albumdle, persondle
from games.immichdle.game import MODE_ALBUM, MODE_PERSON
from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService

_BUILD_SPEC = {MODE_PERSON: persondle.build_spec, MODE_ALBUM: albumdle.build_spec}
_GAME_KWARGS = {MODE_PERSON: persondle.game_kwargs, MODE_ALBUM: albumdle.game_kwargs}


def build_spec(mode: str, immich_service: ContentQueries, settings: dict[str, float]) -> dict[str, Any]:
    return _BUILD_SPEC[mode](immich_service, settings)


def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
    return {UUID(spec["target"]["id"])}


def game_kwargs(
    mode: str,
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    return _GAME_KWARGS[mode](
        spec, settings, rounds_played=rounds_played, immich_service=immich_service, ml_service=ml_service
    )
