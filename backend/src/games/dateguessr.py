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

FLAT_SCORE_DAYS = 0
DECAY_DAYS = 500.0

# Minimum number of days a new round's asset should keep from every previous round's true date, so
# rounds don't end up testing near-duplicate dates. Best-effort - see games/asset_rounds.py's
# pick_spread_asset. Mirrors geoguessr.py's _MIN_CANDIDATE_SEPARATION_KM.
_MIN_CANDIDATE_SEPARATION_DAYS = 100


@dataclass(frozen=True)
class AssetSnapshot:
    """An asset's id/date frozen at the moment a round was created - not a live query result, so a
    round's answer stays stable even if the underlying Immich data changes later (same rationale as
    more_or_less.py's PersonSnapshot / geoguessr.py's AssetSnapshot)."""

    id: UUID
    date: date

    @classmethod
    def of(cls, asset: Asset) -> "AssetSnapshot":
        # Local calendar day, not the UTC day of file_created_at - the guess is compared day-exact,
        # so a photo taken late in the local evening must not read as the next (UTC) day. See
        # domain/asset.py's local_date.
        return cls(id=asset.id, date=asset.local_date)

    def to_dict(self) -> dict[str, Any]:
        return {"id": str(self.id), "date": self.date.isoformat()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetSnapshot":
        return cls(id=UUID(data["id"]), date=date.fromisoformat(data["date"]))


class DateguessrRound(BaseRound):
    def __init__(
        self,
        id: UUID,
        game_id: UUID,
        round_index: int,
        asset: AssetSnapshot,
        extras: list[AssetSnapshot] | None = None,
    ) -> None:
        extras = extras or []
        super().__init__(id, game_id, round_index, shown_entities=[asset.id] + [extra.id for extra in extras])
        self.asset = asset
        self.extras = extras
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
        return {
            "asset": self.asset.to_dict(),
            "extras": [extra.to_dict() for extra in self.extras],
            "guess": self.guess.isoformat() if self.guess else None,
        }

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "DateguessrRound":
        round_ = cls(
            id=id,
            game_id=game_id,
            round_index=round_index,
            asset=AssetSnapshot.from_dict(payload["asset"]),
            extras=[AssetSnapshot.from_dict(extra) for extra in payload.get("extras", [])],
        )
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

    def _query_extra_assets(self, main: Asset, exclude_ids: frozenset[UUID], *, limit: int) -> list[Asset]:
        return self._immich_service.get_assets(
            media_type="photo",
            local_date=main.local_date,
            random=True,
            limit=limit,
            exclude_ids=exclude_ids,
        )

    def _make_round(self, round_index: int, asset: Asset, extras: list[Asset]) -> DateguessrRound:
        return DateguessrRound(
            id=uuid4(),
            game_id=self.id,
            round_index=round_index,
            asset=AssetSnapshot.of(asset),
            extras=[AssetSnapshot.of(extra) for extra in extras],
        )

    def _separation(self, candidate: Asset, answer: date) -> float:
        return abs((candidate.local_date - answer).days)

    def _previous_answers(self) -> list[date]:
        return [round_.asset.date for round_ in self.rounds]
