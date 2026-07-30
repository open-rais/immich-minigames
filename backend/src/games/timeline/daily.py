"""Roadmap #G (daily games) - Timeline's DailySupport implementation (games/daily.py's contract):
generates a day's shared content, decides which ids future days must avoid repeating, and builds
the kwargs to replay it against the *same* TimelineGame class a normal game uses (see
docs/TODO/DECOUPLING.md decision C)."""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from domain.asset import Asset
from games.timeline.game import CardSnapshot, LiveContent, TimelineGame
from services.immich_service import ImmichService
from services.ml_service import MLService


def _placeholder_asset(id: UUID, *, local_date: date) -> Asset:
    """A minimal, otherwise-unused Asset carrying only the field(s) CardSnapshot.of() actually
    reads (id + local_date) - ScriptedContent already knows the real snapshot content directly
    (from the spec), so this only exists to satisfy TimelineGame's content -> TimelineRound
    pipeline, which is typed around the domain Asset LiveContent queries Immich for."""
    return Asset(
        id=id,
        type="IMAGE",
        file_created_at=datetime.min,
        local_date=local_date,
        original_file_name="",
        width=None,
        height=None,
        is_favorite=False,
        latitude=None,
        longitude=None,
        city=None,
        state=None,
        country=None,
    )


class ScriptedContent:
    """Replays a pre-generated chain of cards instead of querying Immich live - the daily
    counterpart to games/timeline/game.py's LiveContent. `next_index` resumes mid-game when
    reconstructing an in-progress daily game (see game_kwargs below). Ignores `exclude_ids`/
    `min_separation_days` entirely - the chain was already built with those rules applied at
    generation time (build_spec below), so re-applying them here would be redundant."""

    def __init__(self, cards: list[CardSnapshot], next_index: int) -> None:
        self._cards = cards
        self._next_index = next_index

    def pick_card(
        self, exclude_ids: frozenset[UUID], board_dates: list[date], *, min_separation_days: int
    ) -> Asset | None:
        if self._next_index >= len(self._cards):
            return None
        card = self._cards[self._next_index]
        self._next_index += 1
        return _placeholder_asset(card.id, local_date=card.date)

    def has_more(self, exclude_ids: frozenset[UUID]) -> bool:
        return self._next_index < len(self._cards)


def build_spec(mode: str, immich_service: ImmichService, settings: dict[str, float]) -> dict[str, Any]:
    # TimelineGame.has_next_round() checks the *previous* round's score_delta (a real guess) -
    # meaningless for a precomputed chain, so this drives create_next_round() directly for a fixed
    # length instead, the same reason (and shape) as games/more_or_less/daily.py's own build_spec.
    chain_length = int(settings.get("chain_length", 100))
    game = TimelineGame.start(id=uuid4(), content=LiveContent(immich_service), settings=settings)
    cards = [game.rounds[0].board[0], game.rounds[0].card]
    while len(cards) < chain_length + 1:
        next_round = game.create_next_round()
        cards.append(next_round.card)
        game.rounds.append(next_round)
    return {"cards": [card.to_dict() for card in cards]}


def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
    # Every card in the spec is answer-content (no decorative extras, unlike Geoguessr/Dateguessr's
    # extra photos) - all of it must stay out of a future day's chain.
    return {UUID(card["id"]) for card in spec["cards"]}


def game_kwargs(
    mode: str,
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    cards = [CardSnapshot.from_dict(c) for c in spec["cards"]]
    # start() consumes cards[0] (the initial board seed) *and* cards[1] (the first card to place)
    # in one shot - the same MoreOrLess/Dateguessr-style jump: the "next fresh index" goes from 0
    # straight to 2 after round 1, not 1, or a resumed game would re-draw cards[1] as if still
    # fresh (see games/more_or_less/daily.py's game_kwargs for the same reasoning in full).
    next_index = rounds_played + 1 if rounds_played > 0 else 0
    return {"content": ScriptedContent(cards, next_index), "settings": settings}
