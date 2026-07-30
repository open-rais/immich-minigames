"""
Based on the Timeline board game. Photos are "cards" with their date printed below - the player
starts with one card already placed (date visible) and, round after round, must insert a new card
(date hidden) into the chronologically correct slot relative to the cards already on the board. A
correct guess chains into a new round (the new card joins the board at its real position); a wrong
guess ends the game (score = the streak of correctly placed cards). See docs/GAMES/TIMELINE.md and
docs/TODO/TIMELINE.md (design doc, decisions [A]-[K]).

Mirrors Dateguessr's split of *which* asset a round gets (`TimelineContent` protocol - live Immich
queries here, a frozen daily spec in games/timeline/daily.py's ScriptedContent) from the game loop
itself (insertion, board, scoring), which lives entirely here - docs/TODO/DECOUPLING.md decision
[J]: zero logic shared with any other game beyond games/shared/'s pure helpers.
"""

import bisect
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from domain.asset import Asset
from games.base import BaseGame, BaseRound
from games.shared.picking import pick_spread_asset
from games.shared.serialization import DictCodec
from services.immich_service import ImmichService

GAME_TYPE = "timeline"
MODE_ARCADE = "arcade"

TOLERANCE_DAYS = 1
MIN_SEPARATION_DAYS = 30
MAX_CARDS = 0  # 0 = no limit - decision [F]

# How many random photos to sample when looking for one far enough from every card already on the
# board - see games/shared/picking.py's pick_spread_asset. Same role as Dateguessr's homonymous
# constant.
_CANDIDATE_SAMPLE_SIZE = 10


@dataclass(frozen=True)
class CardSnapshot(DictCodec):
    """A card's id/date frozen at the moment it was drawn - not a live query result, so a round's
    board/answer stay stable even if the underlying Immich data changes later (same rationale as
    Dateguessr's AssetSnapshot)."""

    id: UUID
    date: date

    @classmethod
    def of(cls, asset: Asset) -> "CardSnapshot":
        # Local calendar day, not the UTC day of file_created_at - see domain/asset.py's local_date
        # and decision [C].
        return cls(id=asset.id, date=asset.local_date)


class TimelineContent(Protocol):
    """The single point of variation between a normal Timeline game and a daily one (decision [G]) -
    live Immich queries (LiveContent below) vs. a frozen daily spec (games/timeline/daily.py's
    ScriptedContent). The game engine below never knows which."""

    def pick_card(
        self, exclude_ids: frozenset[UUID], board_dates: list[date], *, min_separation_days: int
    ) -> Asset | None:
        """The next card to draw, excluding `exclude_ids` and preferring one at least
        `min_separation_days` from every date already on the board (see games/shared/picking.py's
        pick_spread_asset) - None when no eligible asset is left."""
        ...

    def has_more(self, exclude_ids: frozenset[UUID]) -> bool:
        """Whether another card is available, without actually picking one - used by
        has_next_round() so it doesn't have to look at a guess to decide (unlike MoreOrLess's
        chain, this game's next card doesn't depend on what was guessed)."""
        ...


class LiveContent:
    """Normal-play TimelineContent - samples eligible photos straight from Immich."""

    def __init__(self, immich_service: ImmichService) -> None:
        self._immich_service = immich_service

    def _query_assets(self, exclude_ids: frozenset[UUID], *, limit: int, randomize: bool) -> list[Asset]:
        return self._immich_service.get_assets(
            media_type="photo", randomize=randomize, limit=limit, exclude_ids=exclude_ids
        )

    @staticmethod
    def _separation(candidate: Asset, board_date: date) -> float:
        return abs((candidate.local_date - board_date).days)

    def pick_card(
        self, exclude_ids: frozenset[UUID], board_dates: list[date], *, min_separation_days: int
    ) -> Asset | None:
        candidates = self._query_assets(exclude_ids, limit=_CANDIDATE_SAMPLE_SIZE, randomize=True)
        return pick_spread_asset(candidates, board_dates, self._separation, min_separation_days)

    def has_more(self, exclude_ids: frozenset[UUID]) -> bool:
        # Cheap existence check - pick_card()'s separation-aware pick always succeeds as long as the
        # candidate pool isn't empty (see pick_spread_asset's fallback), so this is consistent with
        # it without needing to sample _CANDIDATE_SAMPLE_SIZE rows twice.
        return bool(self._query_assets(exclude_ids, limit=1, randomize=False))


class TimelineRound(BaseRound):
    def __init__(
        self, id: UUID, game_id: UUID, round_index: int, board: list[CardSnapshot], card: CardSnapshot
    ) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[card.id] + [c.id for c in board])
        self.board = board
        self.card = card
        self.guess: int | None = None

    @property
    def correct_slot(self) -> int:
        """How many board cards are strictly earlier than `card` - the exact insertion index
        (`list.insert(i, x)` semantics, decision §2) that keeps the board chronologically correct.
        With duplicate dates on the board, this always lands right before the first equal-or-later
        one - fine, since accepted_slots() below is what actually decides whether a guess counts."""
        dates = [c.date for c in self.board]
        return bisect.bisect_left(dates, self.card.date)

    def accepted_slots(self, tolerance_days: int) -> range:
        """Every slot whose neighbors don't contradict `card`'s real date beyond `tolerance_days` -
        decision [D]. Always contains correct_slot, and is always a contiguous range: the left
        condition below is true for a prefix of slots (board[i-1] only grows as i grows) and the
        right condition true for a suffix (board[i] only grows too), so their intersection is a
        single interval."""
        dates = [c.date for c in self.board]
        tol = timedelta(days=tolerance_days)
        valid = [
            i
            for i in range(len(dates) + 1)
            if (i == 0 or dates[i - 1] <= self.card.date + tol)
            and (i == len(dates) or dates[i] >= self.card.date - tol)
        ]
        return range(valid[0], valid[-1] + 1)

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        settings = settings or {}
        tolerance_days = int(settings.get("tolerance_days", TOLERANCE_DAYS))
        return 1 if self.guess in self.accepted_slots(tolerance_days) else 0

    @property
    def correct(self) -> bool | None:
        """Whether the guess landed in an accepted slot - None until answered. Mirrors
        MoreOrLessRound.correct as the single definition of "correct" for the DTOs."""
        if not self.answered:
            return None
        return self.score_delta == 1

    def to_payload(self) -> dict[str, Any]:
        return {
            "board": [c.to_dict() for c in self.board],
            "card": self.card.to_dict(),
            "guess": self.guess,
        }

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "TimelineRound":
        round_ = cls(
            id=id,
            game_id=game_id,
            round_index=round_index,
            board=[CardSnapshot.from_dict(c) for c in payload["board"]],
            card=CardSnapshot.from_dict(payload["card"]),
        )
        round_.guess = payload["guess"]
        round_.score_delta = score_delta
        return round_


class TimelineGame(BaseGame):
    game_type = GAME_TYPE
    mode = MODE_ARCADE
    _not_enough_assets_message = "not enough photos in Immich to start a Timeline game"

    def __init__(
        self,
        id: UUID,
        rounds: list[BaseRound],
        content: TimelineContent,
        score: int = 0,
        finished: bool = False,
        settings: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            game_type=self.game_type,
            mode=self.mode,
            rounds=rounds,
            score=score,
            finished=finished,
            settings=settings,
        )
        self._content = content

    # -- admin-configurable (ADMIN-FEATURE.md point #4, see services/game_settings.py) ----------

    @property
    def _tolerance_days(self) -> int:
        return int(self._settings.get("tolerance_days", TOLERANCE_DAYS))

    @property
    def _min_separation_days(self) -> int:
        return int(self._settings.get("min_separation_days", MIN_SEPARATION_DAYS))

    @property
    def _max_cards(self) -> int:
        return int(self._settings.get("max_cards", MAX_CARDS))

    # -- game loop ------------------------------------------------------------

    @property
    def _shown_asset_ids(self) -> frozenset[UUID]:
        # Flattens every round's shown_entities (board + the card being placed), so an asset already
        # shown this game - whether on the board or as a still-pending card - is never picked again.
        return frozenset(id_ for round_ in self.rounds for id_ in round_.shown_entities)

    @classmethod
    def start(
        cls, id: UUID, content: TimelineContent, settings: Mapping[str, float] | None = None
    ) -> "TimelineGame":
        game = cls(id=id, rounds=[], content=content, settings=settings)
        min_separation_days = game._min_separation_days

        initial = content.pick_card(frozenset(), [], min_separation_days=min_separation_days)
        if initial is None:
            raise ValueError(cls._not_enough_assets_message)
        initial_card = CardSnapshot.of(initial)

        next_card = content.pick_card(
            frozenset({initial.id}), [initial_card.date], min_separation_days=min_separation_days
        )
        if next_card is None:
            raise ValueError(cls._not_enough_assets_message)

        first_round = TimelineRound(
            id=uuid4(),
            game_id=id,
            round_index=1,
            board=[initial_card],
            card=CardSnapshot.of(next_card),
        )
        game.rounds.append(first_round)
        return game

    def has_next_round(self) -> bool:
        current = self.current_round
        if current.score_delta != 1:
            return False
        max_cards = self._max_cards
        if max_cards and current.round_index + 1 >= max_cards:
            # Total cards ever drawn (the round-1 initial board card + one per round played) has
            # reached the admin-configured cap - ends as a perfect run, not a loss, decision [F].
            return False
        return self._content.has_more(self._shown_asset_ids)

    def create_next_round(self) -> BaseRound:
        previous = self.current_round
        board = list(previous.board)
        board.insert(previous.correct_slot, previous.card)

        exclude_ids = self._shown_asset_ids
        next_card = self._content.pick_card(
            exclude_ids, [c.date for c in board], min_separation_days=self._min_separation_days
        )
        if next_card is None:
            raise ValueError("no more eligible assets left - has_next_round() should have returned False")

        return TimelineRound(
            id=uuid4(),
            game_id=self.id,
            round_index=previous.round_index + 1,
            board=board,
            card=CardSnapshot.of(next_card),
        )
