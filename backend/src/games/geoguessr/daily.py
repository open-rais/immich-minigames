"""Geoguessr's DailySupport implementation (games/daily.py's contract): generates a day's shared
content, decides which ids future days must avoid repeating, and builds the kwargs to replay it
against the *same* GeoguessrGame class a normal game uses."""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from domain.asset import Asset
from games.geoguessr.content import LiveContent
from games.geoguessr.game import GeoguessrGame
from games.geoguessr.round import AssetSnapshot
from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService


def _placeholder_asset(id: UUID, *, latitude: float, longitude: float) -> Asset:
    """A minimal, otherwise-unused Asset carrying only the field(s) AssetSnapshot.of() actually
    reads (id + latitude/longitude) - ScriptedContent already knows the real snapshot content
    directly (from the spec), so this only exists to satisfy GeoguessrGame's
    content -> _make_round pipeline, which is typed around the domain Asset LiveContent queries
    Immich for."""
    return Asset(
        id=id,
        type="IMAGE",
        file_created_at=datetime.min,
        local_date=date.min,
        original_file_name="",
        width=None,
        height=None,
        is_favorite=False,
        latitude=latitude,
        longitude=longitude,
        city=None,
        state=None,
        country=None,
    )


class ScriptedContent:
    """Replays a pre-generated `daily_challenges.spec['rounds']` instead of querying Immich live -
    the daily counterpart to games/geoguessr/game.py's LiveContent. `next_index` resumes mid-game
    when reconstructing an in-progress daily game (see game_kwargs below)."""

    def __init__(self, rounds_spec: list[dict[str, Any]], next_index: int = 0) -> None:
        self._rounds_spec = rounds_spec
        self._next_index = next_index
        # This round's spec entry, set by pick_asset and read right after by pick_extras - the game
        # always calls them as a pair for the same round before advancing, mirroring how the
        # original daily_scripted.py's DailyGeoguessrGame derived both from the same spec index.
        self._current: dict[str, Any] | None = None

    def pick_asset(self, exclude_ids: frozenset[UUID], previous_answers: list[tuple[float, float]]) -> Asset | None:
        if self._next_index >= len(self._rounds_spec):
            return None
        self._current = self._rounds_spec[self._next_index]
        self._next_index += 1
        snapshot = AssetSnapshot.from_dict(self._current["main"])
        return _placeholder_asset(snapshot.id, latitude=snapshot.latitude, longitude=snapshot.longitude)

    def pick_extras(self, main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        assert self._current is not None, "pick_extras called before pick_asset for this round"
        extras = [AssetSnapshot.from_dict(e) for e in self._current["extras"]]
        return [_placeholder_asset(e.id, latitude=e.latitude, longitude=e.longitude) for e in extras]

    def has_more(self, exclude_ids: frozenset[UUID]) -> bool:
        return self._next_index < len(self._rounds_spec)


def build_spec(mode: str, immich_service: ContentQueries, settings: dict[str, float]) -> dict[str, Any]:
    # GeoguessrGame.has_next_round() never looks at the previous round's guess - it's already
    # guess-independent, so the real has_next_round()/create_next_round() pair can drive this loop
    # as-is, on a throwaway game built from live content.
    game = GeoguessrGame.start(id=uuid4(), content=LiveContent(immich_service), settings=settings)
    total_rounds = game.total_rounds
    while len(game.rounds) < total_rounds:
        if not game.has_next_round():
            raise ValueError(f"not enough content to fill {total_rounds} daily rounds for geoguessr/{mode}")
        game.rounds.append(game.create_next_round())
    return {
        "rounds": [
            {"main": round_.asset.to_dict(), "extras": [extra.to_dict() for extra in round_.extras]}
            for round_ in game.rounds
        ]
    }


def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
    return {UUID(round_["main"]["id"]) for round_ in spec["rounds"]}


def game_kwargs(
    mode: str,
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    return {"content": ScriptedContent(spec["rounds"], next_index=rounds_played), "settings": settings}
