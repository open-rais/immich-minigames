"""
Shared skeleton for the "place a single asset, N fixed rounds, score by closeness" games
(Geoguessr, Dateguessr) - see docs/GAMES/GEOGUESSR.md / DATEGUESSR.md for each game's specifics.

Both games play a fixed number of rounds (a wrong guess doesn't end the game early), show one
asset per round, and score each round on a shared exponential-decay curve. They differ only in the
metric (great-circle km vs. calendar days), the per-round snapshot, and which assets are eligible
(Geoguessr needs a location). This module owns everything that doesn't depend on those differences;
concrete games fill in the abstract hooks below.
"""

import math
from abc import abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

from domain.asset import Asset
from games.base import BaseGame, BaseRound
from services.immich_service import ImmichService

TOTAL_ROUNDS = 5
MAX_SCORE = 5000

# How many random photos to sample when looking for one far enough from every previous round's
# answer - see pick_spread_asset. Not required for correctness (falls back to the first candidate if
# none qualifies) - just keeps rounds spread out instead of clustering on near-duplicate answers.
_CANDIDATE_SAMPLE_SIZE = 10

_Answer = TypeVar("_Answer")


def exp_decay_score(distance: float, flat_zone: float, decay: float, max_score: int = MAX_SCORE) -> int:
    """The shared per-round score curve: `max_score` within a flat zone around the exact answer,
    then `round(max_score * exp(-distance / decay))` beyond it, floored at 0. `distance` and its
    units are game-specific (km for Geoguessr, days for Dateguessr)."""
    if distance <= flat_zone:
        return max_score
    return max(0, round(max_score * math.exp(-distance / decay)))


def pick_spread_asset(
    candidates: list[Asset],
    previous_answers: list[_Answer],
    separation: Callable[[Asset, _Answer], float],
    min_separation: float,
) -> Asset | None:
    """Prefers the first candidate at least `min_separation` away (by `separation`) from every
    previous round's answer, so rounds don't test near-duplicate answers. Falls back to the first
    candidate if none qualifies, or None if there are no candidates at all."""
    if not candidates:
        return None
    for candidate in candidates:
        if all(separation(candidate, answer) >= min_separation for answer in previous_answers):
            return candidate
    return candidates[0]


class AssetRoundsGame(BaseGame):
    # Filled in by each concrete game (see GeoguessrGame / DateguessrGame).
    game_type: str
    mode: str
    _min_separation: float
    _not_enough_assets_message: str

    def __init__(
        self,
        id: UUID,
        owner: str,
        rounds: list[BaseRound],
        immich_service: ImmichService,
        score: int = 0,
        finished: bool = False,
    ) -> None:
        super().__init__(
            id=id,
            owner=owner,
            game_type=self.game_type,
            mode=self.mode,
            rounds=rounds,
            score=score,
            finished=finished,
        )
        self._immich_service = immich_service

    # -- hooks concrete games implement ------------------------------------

    @abstractmethod
    def _query_assets(self, exclude_ids: frozenset[UUID], *, limit: int, random: bool) -> list[Asset]:
        """The assets eligible for this game (e.g. Geoguessr additionally requires a location)."""

    @abstractmethod
    def _make_round(self, round_index: int, asset: Asset) -> BaseRound:
        """Build a concrete round from a freshly-picked asset (snapshotting it in the process)."""

    @abstractmethod
    def _separation(self, candidate: Asset, answer: Any) -> float:
        """Distance (in this game's metric) between a candidate asset and a previous round's answer
        - used with `_min_separation` to keep rounds spread out."""

    @abstractmethod
    def _previous_answers(self) -> list[Any]:
        """The already-played rounds' answers, in the shape `_separation` expects."""

    # -- shared game loop ---------------------------------------------------

    @property
    def _shown_asset_ids(self) -> frozenset[UUID]:
        # Every round shows exactly one asset (its first/only shown entity), so this works without
        # reaching into each game's round-specific `.asset` attribute.
        return frozenset(round_.shown_entities[0] for round_ in self.rounds)

    def _pick_asset(self, exclude_ids: frozenset[UUID]) -> Asset | None:
        candidates = self._query_assets(exclude_ids, limit=_CANDIDATE_SAMPLE_SIZE, random=True)
        return pick_spread_asset(candidates, self._previous_answers(), self._separation, self._min_separation)

    @classmethod
    def start(cls, id: UUID, owner: str, immich_service: ImmichService) -> "AssetRoundsGame":
        game = cls(id=id, owner=owner, rounds=[], immich_service=immich_service)
        asset = game._pick_asset(exclude_ids=frozenset())
        if asset is None:
            raise ValueError(cls._not_enough_assets_message)
        game.rounds.append(game._make_round(round_index=1, asset=asset))
        return game

    def has_next_round(self) -> bool:
        if self.current_round.round_index >= TOTAL_ROUNDS:
            return False
        # Cheap existence check - create_next_round()'s separation-aware pick always succeeds as long
        # as the candidate pool isn't empty (see pick_spread_asset's fallback), so this is consistent
        # with it without needing to sample _CANDIDATE_SAMPLE_SIZE rows twice.
        remaining = self._query_assets(self._shown_asset_ids, limit=1, random=False)
        return bool(remaining)

    def create_next_round(self) -> BaseRound:
        asset = self._pick_asset(self._shown_asset_ids)
        if asset is None:
            raise ValueError("no more eligible assets left - has_next_round() should have returned False")
        return self._make_round(round_index=self.current_round.round_index + 1, asset=asset)
