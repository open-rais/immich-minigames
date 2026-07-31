"""The single point of variation between a normal Dateguessr game and a daily one -
live Immich queries (LiveContent below) vs. a frozen daily spec (games/dateguessr/daily.py's
ScriptedContent). games/dateguessr/game.py's DateguessrGame never knows which."""

from datetime import date
from typing import Protocol
from uuid import UUID

from domain.asset import Asset
from games.shared.picking import pick_spread_asset
from services.immich import ContentQueries

# How many random photos to sample when looking for one far enough from every previous round's
# answer - see games/shared/picking.py's pick_spread_asset. Not required for correctness (falls
# back to the first candidate if none qualifies) - just keeps rounds spread out instead of
# clustering on near-duplicate answers.
_CANDIDATE_SAMPLE_SIZE = 10

# How many random candidates to sample when looking for extras - mirrors _CANDIDATE_SAMPLE_SIZE's
# rationale, just sized a bit larger since up to MAX_EXTRA_ASSETS of them are kept at once instead
# of just one.
_EXTRA_CANDIDATE_SAMPLE_SIZE = 10

# Minimum number of days a new round's asset should keep from every previous round's true date, so
# rounds don't end up testing near-duplicate dates. Best-effort - see games/shared/picking.py's
# pick_spread_asset. Mirrors geoguessr/content.py's _MIN_CANDIDATE_SEPARATION_KM.
_MIN_CANDIDATE_SEPARATION_DAYS = 100


class DateguessrContent(Protocol):
    """The single point of variation between a normal Dateguessr game and a daily one -
    live Immich queries (LiveContent below) vs. a frozen daily spec (games/dateguessr/daily.py's
    ScriptedContent). The game engine below never knows which."""

    def pick_asset(self, exclude_ids: frozenset[UUID], previous_answers: list[date]) -> Asset | None:
        """The next round's main asset, excluding `exclude_ids` and preferring one far enough from
        every entry in `previous_answers` (see games/shared/picking.py's pick_spread_asset) - None
        when no eligible asset is left."""
        ...

    def pick_extras(self, main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        """Up to `limit` decorative photos to show alongside `main` this round."""
        ...

    def has_more(self, exclude_ids: frozenset[UUID]) -> bool:
        """Whether another round's worth of content is available, without actually picking it -
        used by has_next_round() so it doesn't have to look at a guess to decide (this game's
        rounds are guess-independent, unlike MoreOrLess's chain)."""
        ...


class LiveContent:
    """Normal-play DateguessrContent - samples eligible assets straight from Immich."""

    def __init__(self, immich_service: ContentQueries) -> None:
        self._immich_service = immich_service

    def _query_assets(self, exclude_ids: frozenset[UUID], *, limit: int, randomize: bool) -> list[Asset]:
        return self._immich_service.get_assets(
            media_type="photo", randomize=randomize, limit=limit, exclude_ids=exclude_ids
        )

    def _query_extra_assets(self, main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        return self._immich_service.get_assets(
            media_type="photo",
            local_date=main.local_date,
            randomize=True,
            limit=limit,
            exclude_ids=exclude_ids,
        )

    @staticmethod
    def _separation(candidate: Asset, answer: date) -> float:
        return abs((candidate.local_date - answer).days)

    def pick_asset(self, exclude_ids: frozenset[UUID], previous_answers: list[date]) -> Asset | None:
        candidates = self._query_assets(exclude_ids, limit=_CANDIDATE_SAMPLE_SIZE, randomize=True)
        return pick_spread_asset(candidates, previous_answers, self._separation, _MIN_CANDIDATE_SEPARATION_DAYS)

    def pick_extras(self, main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        candidates = self._query_extra_assets(main, exclude_ids, limit=_EXTRA_CANDIDATE_SAMPLE_SIZE)
        return candidates[:limit]

    def has_more(self, exclude_ids: frozenset[UUID]) -> bool:
        # Cheap existence check - pick_asset()'s separation-aware pick always succeeds as long as
        # the candidate pool isn't empty (see pick_spread_asset's fallback), so this is consistent
        # with it without needing to sample _CANDIDATE_SAMPLE_SIZE rows twice.
        return bool(self._query_assets(exclude_ids, limit=1, randomize=False))
