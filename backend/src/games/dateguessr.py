"""
Same idea as Geoguessr, on a timeline instead of a map. A single asset is shown - the player marks
a day on a timeline guessing when it was taken. 5 rounds are always played (unlike MoreOrLess, a
wrong guess doesn't end the game early), and the final score is the sum of all 5 rounds' scores.
See docs/GAMES/DATEGUESSR.md.

The fixed-rounds game loop (round count, candidate picking, next-round creation, exponential-decay
scoring) lives in games/asset_rounds.py and is shared with Geoguessr - only the date metric and
per-round snapshot are Dateguessr-specific and live here.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from domain.asset import Asset
from games.asset_rounds import MAX_SCORE, TOTAL_ROUNDS, AssetRoundsGame, exp_decay_score  # noqa: F401 (MAX_SCORE/TOTAL_ROUNDS re-exported for tests)
from games.base import BaseRound

GAME_TYPE = "dateguessr"
MODE_DAYS_TO_DATE = "daysToDate"

# Unlike Geoguessr's 1km flat-score radius, there's no slack here - the guess is always day-exact by
# construction (see docs/GAMES/DATEGUESSR.md: "acertar la fecha exacta da el máximo"), so only an
# exact match scores the max.
FLAT_SCORE_DAYS = 0
# Beyond an exact match: score = round(MAX_SCORE * exp(-days_off / DECAY_DAYS)). Calibrated against
# the dev library's real spread (fileCreatedAt ranges ~2008-09-16 to ~2026-06-21, ~18 years) so a
# decent-but-not-exact guess still scores something: ~1839pts at 2 years off, ~410pts at 5 years
# off, ~34pts at 10 years off, ~1pt at the full ~18-year spread. First-pass value, meant to be tuned
# once playable - same treatment as geoguessr.py's DECAY_KM.
DECAY_DAYS = 730.0

# Minimum number of days a new round's asset should keep from every previous round's true date, so
# rounds don't end up testing near-duplicate dates. Best-effort - see games/asset_rounds.py's
# pick_spread_asset. Mirrors geoguessr.py's _MIN_CANDIDATE_SEPARATION_KM.
_MIN_CANDIDATE_SEPARATION_DAYS = 60


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
        return exp_decay_score(self.days_off, FLAT_SCORE_DAYS, DECAY_DAYS)

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


class DateguessrGame(AssetRoundsGame):
    game_type = GAME_TYPE
    mode = MODE_DAYS_TO_DATE
    _min_separation = _MIN_CANDIDATE_SEPARATION_DAYS
    _not_enough_assets_message = "not enough photos in Immich to start a Dateguessr game"

    def _query_assets(self, exclude_ids: frozenset[UUID], *, limit: int, random: bool) -> list[Asset]:
        return self._immich_service.get_assets(
            media_type="photo", random=random, limit=limit, exclude_ids=exclude_ids
        )

    def _make_round(self, round_index: int, asset: Asset) -> DateguessrRound:
        return DateguessrRound(id=uuid4(), game_id=self.id, round_index=round_index, asset=AssetSnapshot.of(asset))

    def _separation(self, candidate: Asset, answer: date) -> float:
        return abs((candidate.file_created_at.date() - answer).days)

    def _previous_answers(self) -> list[date]:
        return [round_.asset.date for round_ in self.rounds]
