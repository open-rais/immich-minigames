"""
Based on the Geoguessr game. A single asset is shown - the player marks a day on a timeline
guessing when it was taken. 5 rounds are always played (unlike MoreOrLess, a wrong guess doesn't
end the game early), and the final score is the sum of all 5 rounds' scores. See
docs/GAMES/DATEGUESSR.md.
"""

import math
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from domain.asset import Asset
from games.base import BaseGame, BaseRound
from services.immich_service import ImmichService

GAME_TYPE = "dateguessr"
MODE_DAYS_TO_DATE = "daysToDate"

TOTAL_ROUNDS = 5
MAX_SCORE = 5000
# Unlike Geoguessr's 1km flat-score radius, there's no slack here - the guess is always day-exact
# by construction (see docs/GAMES/DATEGUESSR.md: "acertar la fecha exacta da el máximo"), so only
# an exact match scores the max.
FLAT_SCORE_DAYS = 0
# Beyond an exact match: score = round(MAX_SCORE * exp(-days_off / DECAY_DAYS)). Calibrated against
# the dev library's real spread (fileCreatedAt ranges ~2008-09-16 to ~2026-06-21, ~18 years) so a
# decent-but-not-exact guess still scores something: ~1839pts at 2 years off, ~410pts at 5 years
# off, ~34pts at 10 years off, ~1pt at the full ~18-year spread. First-pass value, meant to be
# tuned once playable - same treatment as geoguessr.py's DECAY_KM.
DECAY_DAYS = 730.0

# How many random photos to sample when looking for one far enough in time from every previous
# round's true date - see _pick_asset. Not required for correctness (falls back to the first
# candidate if none qualifies) - just keeps rounds spread out instead of clustering on nearby
# dates. Mirrors geoguessr.py's _CANDIDATE_SAMPLE_SIZE/_MIN_CANDIDATE_SEPARATION_KM.
_CANDIDATE_SAMPLE_SIZE = 10
_MIN_CANDIDATE_SEPARATION_DAYS = 60


def _score_for_days(days_off: int) -> int:
    if days_off <= FLAT_SCORE_DAYS:
        return MAX_SCORE
    return max(0, round(MAX_SCORE * math.exp(-days_off / DECAY_DAYS)))


@dataclass(frozen=True)
class AssetSnapshot:
    """An asset's id/date frozen at the moment a round was created - not a live query result, so a
    round's answer stays stable even if the underlying Immich data changes later (same rationale as
    more_or_less.py's PersonSnapshot / geoguessr.py's AssetSnapshot)."""

    id: UUID
    date: date

    @classmethod
    def of(cls, asset: Asset) -> "AssetSnapshot":
        return cls(id=asset.id, date=asset.file_created_at.date())

    def to_dict(self) -> dict[str, Any]:
        return {"id": str(self.id), "date": self.date.isoformat()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetSnapshot":
        return cls(id=UUID(data["id"]), date=date.fromisoformat(data["date"]))


def _pick_asset(
    immich_service: ImmichService, exclude_ids: frozenset[UUID], previous_dates: list[date]
) -> Asset | None:
    """Samples a few random photos and prefers one far enough in time from every previous round's
    true date, so rounds don't end up testing near-duplicate dates. Falls back to the first
    candidate if none qualifies - mirrors geoguessr.py's _pick_asset."""
    candidates = immich_service.get_assets(
        media_type="photo", random=True, limit=_CANDIDATE_SAMPLE_SIZE, exclude_ids=exclude_ids
    )
    if not candidates:
        return None
    for candidate in candidates:
        candidate_date = candidate.file_created_at.date()
        if all(abs((candidate_date - d).days) >= _MIN_CANDIDATE_SEPARATION_DAYS for d in previous_dates):
            return candidate
    return candidates[0]


class DateguessrRound(BaseRound):
    def __init__(self, id: UUID, game_id: UUID, round_index: int, asset: AssetSnapshot) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[asset.id])
        self.asset = asset
        self.guess: date | None = None

    @property
    def days_off(self) -> int | None:
        if self.guess is None:
            return None
        return abs((self.asset.date - self.guess).days)

    def calculate_score(self) -> int:
        assert self.days_off is not None  # BaseGame.play_round already set self.guess
        return _score_for_days(self.days_off)

    def to_payload(self) -> dict[str, Any]:
        return {"asset": self.asset.to_dict(), "guess": self.guess.isoformat() if self.guess else None}

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "DateguessrRound":
        round_ = cls(id=id, game_id=game_id, round_index=round_index, asset=AssetSnapshot.from_dict(payload["asset"]))
        round_.guess = date.fromisoformat(payload["guess"]) if payload["guess"] else None
        round_.score_delta = score_delta
        return round_


class DateguessrGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        owner: str,
        rounds: list[DateguessrRound],
        immich_service: ImmichService,
        score: int = 0,
        finished: bool = False,
    ) -> None:
        super().__init__(
            id=id,
            owner=owner,
            game_type=GAME_TYPE,
            mode=MODE_DAYS_TO_DATE,
            rounds=rounds,
            score=score,
            finished=finished,
        )
        self._immich_service = immich_service

    @classmethod
    def start(cls, id: UUID, owner: str, immich_service: ImmichService) -> "DateguessrGame":
        asset = _pick_asset(immich_service, exclude_ids=frozenset(), previous_dates=[])
        if asset is None:
            raise ValueError("not enough photos in Immich to start a Dateguessr game")

        first_round = DateguessrRound(id=uuid4(), game_id=id, round_index=1, asset=AssetSnapshot.of(asset))
        return cls(id=id, owner=owner, rounds=[first_round], immich_service=immich_service)

    def _shown_asset_ids(self) -> frozenset[UUID]:
        return frozenset(round_.asset.id for round_ in self.rounds)

    def _previous_dates(self) -> list[date]:
        return [round_.asset.date for round_ in self.rounds]

    def has_next_round(self) -> bool:
        if self.current_round.round_index >= TOTAL_ROUNDS:
            return False
        # Cheap existence check - create_next_round()'s separation-aware pick always succeeds as
        # long as the candidate pool isn't empty (see _pick_asset's fallback), so this is
        # consistent with it without needing to sample _CANDIDATE_SAMPLE_SIZE rows twice.
        remaining = self._immich_service.get_assets(media_type="photo", limit=1, exclude_ids=self._shown_asset_ids())
        return bool(remaining)

    def create_next_round(self) -> DateguessrRound:
        asset = _pick_asset(self._immich_service, self._shown_asset_ids(), self._previous_dates())
        if asset is None:
            raise ValueError("no more photos left - has_next_round() should have returned False")

        return DateguessrRound(
            id=uuid4(),
            game_id=self.id,
            round_index=self.current_round.round_index + 1,
            asset=AssetSnapshot.of(asset),
        )
