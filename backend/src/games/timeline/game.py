"""
Based on the Timeline board game. Photos are "cards" with their date printed below - the player
starts with one card already placed (date visible) and, round after round, must insert a new card
(date hidden) into the chronologically correct slot relative to the cards already on the board. A
correct guess chains into a new round (the new card joins the board at its real position); a wrong
guess ends the game (score = the streak of correctly placed cards). See docs/GAMES/TIMELINE.md and
docs/TODO/TIMELINE.md (design doc, decisions [A]-[K]).

Mirrors Dateguessr's split of *which* asset a round gets (games/timeline/content.py's
TimelineContent protocol - live Immich queries here, a frozen daily spec in
games/timeline/daily.py's ScriptedContent) from the game loop itself (insertion, board
rehydration, scoring), which lives entirely here - docs/TODO/DECOUPLING.md decision [J]: zero
logic shared with any other game beyond games/shared/'s pure helpers. games/timeline/round.py holds
the round itself (its board/card snapshot and accepted-slot/scoring math).
"""

from collections.abc import Mapping
from uuid import UUID, uuid4

from games.base import BaseGame, BaseRound
from games.timeline.content import TimelineContent
from games.timeline.round import TOLERANCE_DAYS, CardSnapshot, TimelineRound

GAME_TYPE = "timeline"
MODE_ARCADE = "arcade"

MIN_SEPARATION_DAYS = 30
MAX_CARDS = 0  # 0 = no limit - decision [F]


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
        self._hydrate_boards()

    def _hydrate_boards(self) -> None:
        # Rebuilds the boards from_payload left empty (rounds >= 2 don't persist theirs - see
        # TimelineRound.to_payload): replays round 1's persisted seed forward, inserting each
        # round's card at its real slot - the same two lines create_next_round runs live, so
        # there's no second definition of "how the board grows" to drift from it. A no-op for
        # boards already present (a game mid-play in memory, or payloads from before the slimming).
        board: list[CardSnapshot] | None = None
        for round_ in self.rounds:
            if board is None:
                board = round_.board  # round 1 always persists its seed board
            elif not round_.board:
                round_._hydrate_board(board)
            next_board = list(round_.board)
            next_board.insert(round_.correct_slot, round_.card)
            board = next_board

    # -- admin-configurable (ADMIN-FEATURE.md point #4, see games/settings_registry.py) ----------

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
        # Every asset ever shown this game - whether on the board or as a still-pending card - so
        # none is picked again. Round 1's seed board plus each round's drawn card is exactly that
        # set (every later board is built from those and nothing else), which keeps this O(R) -
        # flattening every round's shown_entities would revisit the same ids O(R^2) times.
        if not self.rounds:
            return frozenset()
        seed_ids = frozenset(c.id for c in self.rounds[0].board)
        return seed_ids | frozenset(round_.card.id for round_ in self.rounds)

    @classmethod
    def start(cls, id: UUID, content: TimelineContent, settings: Mapping[str, float] | None = None) -> "TimelineGame":
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
