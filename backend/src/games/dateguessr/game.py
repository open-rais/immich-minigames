"""
Same idea as Geoguessr, on a timeline instead of a map. A single asset is shown - the player marks
a day on a timeline guessing when it was taken. 5 rounds are always played (unlike MoreOrLess, a
wrong guess doesn't end the game early), and the final score is the sum of all 5 rounds' scores.
See docs/GAMES/DATEGUESSR.md.

Owns its entire game loop (round count, next-round creation, exponential-decay scoring) -
previously factored out into a shared base class with Geoguessr (games/asset_rounds.py),
deliberately un-shared per docs/TODO/DECOUPLING.md so a change to this game's loop never requires
touching Geoguessr's. *Which* asset/extras a round gets is a separate axis of variation
(games/dateguessr/content.py's DateguessrContent) - live Immich queries normally, a frozen daily
spec for the daily flow (games/dateguessr/daily.py's ScriptedContent) - mirroring how MoreOrLess
already varies its content via CandidateProvider. games/dateguessr/round.py holds the round itself
(its answer snapshot and days-off/scoring math).
"""

from collections.abc import Mapping
from datetime import date
from uuid import UUID, uuid4

from domain.asset import Asset
from games.base import BaseGame, BaseRound
from games.dateguessr.content import DateguessrContent
from games.dateguessr.round import AssetSnapshot, DateguessrRound

GAME_TYPE = "dateguessr"
MODE_DAYS_TO_DATE = "daysToDate"

TOTAL_ROUNDS = 5

# Up to this many additional photos are shown alongside a round's main asset (purely decorative -
# the round's answer/score always stay tied to the main asset only). Fewer are shown if fewer
# qualify - a round is never forced to have exactly 5.
MAX_EXTRA_ASSETS = 4


class DateguessrGame(BaseGame):
    game_type = GAME_TYPE
    mode = MODE_DAYS_TO_DATE
    _not_enough_assets_message = "not enough photos in Immich to start a Dateguessr game"

    def __init__(
        self,
        id: UUID,
        rounds: list[BaseRound],
        content: DateguessrContent,
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

    # -- admin-configurable (ADMIN-FEATURE.md point #4, see games/settings_registry.py) ----------

    @property
    def total_rounds(self) -> int:
        # Public (no leading underscore) - api/dto/common.py's GameOut reads this to show the
        # frontend the *live* round count instead of the hardcoded display-only constant it used to
        # mirror.
        return int(self._settings.get("total_rounds", TOTAL_ROUNDS))

    @property
    def _max_extra_assets(self) -> int:
        return int(self._settings.get("max_extra_assets", MAX_EXTRA_ASSETS))

    # -- round building -------------------------------------------------------

    def _make_round(self, round_index: int, asset: Asset, extras: list[Asset]) -> DateguessrRound:
        return DateguessrRound(
            id=uuid4(),
            game_id=self.id,
            round_index=round_index,
            asset=AssetSnapshot.of(asset),
            extras=[AssetSnapshot.of(extra) for extra in extras],
        )

    def _previous_answers(self) -> list[date]:
        return [round_.asset.date for round_ in self.rounds]

    # -- game loop ------------------------------------------------------------

    @property
    def _shown_asset_ids(self) -> frozenset[UUID]:
        # Flattens every round's shown_entities (main asset + its extras), so an asset already shown
        # this game - whether as a main asset or just as an extra - is never picked again as either.
        return frozenset(id_ for round_ in self.rounds for id_ in round_.shown_entities)

    def _pick_asset(self, exclude_ids: frozenset[UUID]) -> Asset | None:
        return self._content.pick_asset(exclude_ids, self._previous_answers())

    def _pick_extras(self, main: Asset, exclude_ids: frozenset[UUID]) -> list[Asset]:
        return self._content.pick_extras(main, exclude_ids, limit=self._max_extra_assets)

    @classmethod
    def start(
        cls, id: UUID, content: DateguessrContent, settings: Mapping[str, float] | None = None
    ) -> "DateguessrGame":
        game = cls(id=id, rounds=[], content=content, settings=settings)
        asset = game._pick_asset(exclude_ids=frozenset())
        if asset is None:
            raise ValueError(cls._not_enough_assets_message)
        extras = game._pick_extras(asset, exclude_ids=frozenset({asset.id}))
        game.rounds.append(game._make_round(round_index=1, asset=asset, extras=extras))
        return game

    def has_next_round(self) -> bool:
        if self.current_round.round_index >= self.total_rounds:
            return False
        return self._content.has_more(self._shown_asset_ids)

    def create_next_round(self) -> BaseRound:
        asset = self._pick_asset(self._shown_asset_ids)
        if asset is None:
            raise ValueError("no more eligible assets left - has_next_round() should have returned False")
        extras = self._pick_extras(asset, exclude_ids=self._shown_asset_ids | {asset.id})
        return self._make_round(round_index=self.current_round.round_index + 1, asset=asset, extras=extras)
