"""DateguessrRound - a single placed-guess round, its frozen answer snapshot, and the days-off/
scoring math that only the round itself needs. See games/dateguessr/game.py for the loop that
drives rounds and games/dateguessr/content.py for where a round's asset comes from."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from domain.asset import Asset
from games.base import BaseRound
from games.shared.scoring import exp_decay_score
from games.shared.serialization import DictCodec

MAX_SCORE = 5000
FLAT_SCORE_DAYS = 0
DECAY_DAYS = 500.0


@dataclass(frozen=True)
class AssetSnapshot(DictCodec):
    """An asset's id/date frozen at the moment a round was created - not a live query result, so a
    round's answer stays stable even if the underlying Immich data changes later (same rationale as
    more_or_less.py's EntitySnapshot / geoguessr/round.py's AssetSnapshot). The `date` field's
    annotation resolves to the `date` type at class-definition time despite sharing its name (no
    value is bound to `date` in the class namespace by an annotation-only statement) -
    DictCodec.from_dict's `f.type is date` check works correctly, confirmed by this game's
    round-trip test."""

    id: UUID
    date: date

    @classmethod
    def of(cls, asset: Asset) -> "AssetSnapshot":
        # Local calendar day, not the UTC day of file_created_at - the guess is compared day-exact,
        # so a photo taken late in the local evening must not read as the next (UTC) day. See
        # domain/asset.py's local_date.
        return cls(id=asset.id, date=asset.local_date)


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

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        if self.days_off is None:
            raise RuntimeError("calculate_score() called before BaseGame.play_round set self.guess")
        settings = settings or {}
        flat_zone = settings.get("flat_score_days", FLAT_SCORE_DAYS)
        decay = settings.get("decay_days", DECAY_DAYS)
        max_score = int(settings.get("max_score", MAX_SCORE))
        return exp_decay_score(self.days_off, flat_zone, decay, max_score)

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
