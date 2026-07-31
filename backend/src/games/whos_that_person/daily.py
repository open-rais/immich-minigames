"""Who'sThatPerson's DailySupport implementation (games/daily.py's contract): generates a day's
shared content, decides which ids future days must avoid repeating, and builds the kwargs to
replay it against the *same* WhosThatPersonGame class a normal game uses."""

from typing import Any
from uuid import UUID, uuid4

from games.whos_that_person.content import LiveContent
from games.whos_that_person.game import WhosThatPersonGame
from games.whos_that_person.round import HiddenFace
from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService


class ScriptedContent:
    """Replays a pre-generated `daily_challenges.spec['rounds']` instead of querying Immich live -
    the daily counterpart to games/whos_that_person/game.py's LiveContent. `max_faces`/
    `exclude_asset_ids` are ignored - the spec already froze exactly which asset and faces belong
    to this round at generation time. `next_index` resumes mid-game when reconstructing an
    in-progress daily game (see game_kwargs below)."""

    def __init__(self, rounds_spec: list[dict[str, Any]], next_index: int = 0) -> None:
        self._rounds_spec = rounds_spec
        self._next_index = next_index

    def has_more(self, max_faces: int, exclude_asset_ids: frozenset[UUID]) -> bool:
        return self._next_index < len(self._rounds_spec)

    def pick_round(self, max_faces: int, exclude_asset_ids: frozenset[UUID]) -> tuple[UUID, list[HiddenFace]] | None:
        if self._next_index >= len(self._rounds_spec):
            return None
        round_spec = self._rounds_spec[self._next_index]
        self._next_index += 1
        return UUID(round_spec["asset_id"]), [HiddenFace.from_dict(f) for f in round_spec["faces"]]


def build_spec(mode: str, immich_service: ContentQueries, settings: dict[str, float]) -> dict[str, Any]:
    game = WhosThatPersonGame.start(
        id=uuid4(), immich_service=immich_service, content=LiveContent(immich_service), settings=settings
    )
    total_people = game.total_people
    while sum(len(r.faces) for r in game.rounds) < total_people:
        if not game.has_next_round():
            raise ValueError(f"not enough named faces to fill {total_people} daily people for whos-that-person")
        # create_next_round() reads the previous round's ending_streak to seed the next round's
        # incoming_streak - it's 0 here since these rounds are never played (no guess set) while
        # building the spec. Streak is per-player *scoring* state, never part of the shared spec
        # content itself (WhosThatPersonRound.asset_id/faces don't depend on it), so this doesn't
        # affect what actually gets picked.
        game.rounds.append(game.create_next_round())
    return {
        "rounds": [
            {"asset_id": str(round_.asset_id), "faces": [face.to_dict() for face in round_.faces]}
            for round_ in game.rounds
        ]
    }


def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
    # Only the shown asset, not the hidden faces' person ids - get_random_asset_with_named_faces
    # only supports excluding assets (see services/daily_challenge_service.py's
    # _ExcludingImmichService), and
    # repeating the same asset is what actually gives away/duplicates a round; a person reappearing
    # in a *different* photo is fine.
    return {UUID(round_["asset_id"]) for round_ in spec["rounds"]}


def game_kwargs(
    mode: str,
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    return {
        "immich_service": immich_service,
        "content": ScriptedContent(spec["rounds"], next_index=rounds_played),
        "settings": settings,
    }
