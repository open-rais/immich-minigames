"""The single point of variation between a normal Timeline game and a daily one (decision [G]) -
live Immich queries (LiveContent below) vs. a frozen daily spec (games/timeline/daily.py's
ScriptedContent). games/timeline/game.py's TimelineGame never knows which."""

from datetime import date
from typing import Protocol
from uuid import UUID

from domain.asset import Asset
from games.shared.picking import pick_spread_asset
from services.immich import ContentQueries

# How many random photos to sample when looking for one far enough from every card already on the
# board - see games/shared/picking.py's pick_spread_asset. Same role as Dateguessr's homonymous
# constant.
_CANDIDATE_SAMPLE_SIZE = 10


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

    def __init__(self, immich_service: ContentQueries) -> None:
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
