"""TimelineRound - a single card-insertion round, its frozen board/card snapshot, and the
accepted-slot/scoring math that only the round itself needs. See games/timeline/game.py for the
loop that drives rounds (including board rehydration) and games/timeline/content.py for where a
round's card comes from."""

import bisect
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from domain.asset import Asset
from games.base import BaseRound
from games.shared.serialization import DictCodec

TOLERANCE_DAYS = 1


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
        endpoint is the first slot whose left neighbor doesn't undercut `card.date - tol` and the
        right endpoint is the last slot whose right neighbor doesn't overshoot `card.date + tol`,
        so both bounds are plain binary searches on the (sorted) board dates."""
        dates = [c.date for c in self.board]
        tol = timedelta(days=tolerance_days)
        return range(
            bisect.bisect_left(dates, self.card.date - tol),
            bisect.bisect_right(dates, self.card.date + tol) + 1,
        )

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
        payload: dict[str, Any] = {
            "card": self.card.to_dict(),
            "guess": self.guess,
        }
        if self.round_index == 1:
            # Only round 1 persists its board (the single seed card) - every later board is
            # derivable from it (board N = board N-1 + insert(correct_slot, card), exactly what
            # create_next_round does live), so storing each round's whole board would make a
            # game's stored payloads grow O(R^2) with the streak.
            # TimelineGame._hydrate_boards rebuilds the omitted ones at load time.
            payload["board"] = [c.to_dict() for c in self.board]
        return payload

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "TimelineRound":
        round_ = cls(
            id=id,
            game_id=game_id,
            round_index=round_index,
            # Absent for rounds >= 2 (see to_payload) - left empty here and filled in by
            # TimelineGame._hydrate_boards, which sees the whole rounds list; payloads written
            # before boards were slimmed still carry one, and using it when present is the whole
            # backward-compat story.
            board=[CardSnapshot.from_dict(c) for c in payload.get("board", [])],
            card=CardSnapshot.from_dict(payload["card"]),
        )
        round_.guess = payload["guess"]
        round_.score_delta = score_delta
        return round_

    def _hydrate_board(self, board: list[CardSnapshot]) -> None:
        """Fills in a board omitted from this round's persisted payload (see to_payload) - also
        recomputes shown_entities, which __init__ derived from the then-empty board."""
        self.board = board
        self.shown_entities = [self.card.id] + [c.id for c in board]
