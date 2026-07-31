from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

from domain.asset import Asset
from games.timeline import CardSnapshot, TimelineGame, TimelineRound


def _asset(d: date, id: UUID | None = None) -> Asset:
    return Asset(
        id=id or uuid4(),
        type="IMAGE",
        file_created_at=datetime(d.year, d.month, d.day),
        local_date=d,
        original_file_name="",
        width=None,
        height=None,
        is_favorite=False,
        latitude=None,
        longitude=None,
        city=None,
        state=None,
        country=None,
    )


class _FiniteContent:
    """Deterministic TimelineContent test double - plays back a fixed list of assets in order, so
    board-position/exhaustion/max_cards tests don't depend on how many (or which) photos happen to
    be in the dev Immich library."""

    def __init__(self, assets: list[Asset]) -> None:
        self._assets = list(assets)
        self._next = 0

    def pick_card(
        self, exclude_ids: frozenset[UUID], board_dates: list[date], *, min_separation_days: int
    ) -> Asset | None:
        while self._next < len(self._assets):
            asset = self._assets[self._next]
            self._next += 1
            if asset.id not in exclude_ids:
                return asset
        return None

    def has_more(self, exclude_ids: frozenset[UUID]) -> bool:
        return any(a.id not in exclude_ids for a in self._assets[self._next :])


class TestTimelineRoundScoring:
    """Isolated from the DB - constructs rounds directly against known dates."""

    def _round(self, board_dates: list[date], card_date: date) -> TimelineRound:
        board = [CardSnapshot(id=uuid4(), date=d) for d in board_dates]
        card = CardSnapshot(id=uuid4(), date=card_date)
        return TimelineRound(id=uuid4(), game_id=uuid4(), round_index=1, board=board, card=card)

    def test_correct_slot_with_a_single_board_card(self):
        earlier = self._round([date(2020, 6, 1)], date(2020, 1, 1))
        assert earlier.correct_slot == 0

        later = self._round([date(2020, 6, 1)], date(2020, 12, 1))
        assert later.correct_slot == 1

    def test_correct_slot_with_several_board_cards(self):
        round_ = self._round([date(2020, 1, 1), date(2020, 6, 1), date(2020, 12, 1)], date(2020, 7, 1))
        assert round_.correct_slot == 2

    def test_only_the_correct_slot_scores_with_zero_tolerance(self):
        round_ = self._round([date(2020, 1, 1), date(2020, 12, 1)], date(2020, 6, 1))

        round_.guess = round_.correct_slot
        assert round_.calculate_score({"tolerance_days": 0}) == 1

        round_.guess = 0
        assert round_.calculate_score({"tolerance_days": 0}) == 0
        round_.guess = 2
        assert round_.calculate_score({"tolerance_days": 0}) == 0

    def test_tied_dates_accept_both_adjacent_slots(self):
        round_ = self._round([date(2020, 1, 1), date(2020, 6, 1), date(2020, 12, 1)], date(2020, 6, 1))

        assert set(round_.accepted_slots(0)) == {1, 2}

        round_.guess = 1
        assert round_.calculate_score({"tolerance_days": 0}) == 1
        round_.guess = 2
        assert round_.calculate_score({"tolerance_days": 0}) == 1
        round_.guess = 0
        assert round_.calculate_score({"tolerance_days": 0}) == 0

    def test_tolerance_days_widens_the_accepted_range(self):
        round_ = self._round([date(2020, 1, 1), date(2020, 1, 10), date(2020, 1, 20)], date(2020, 1, 4))

        assert set(round_.accepted_slots(0)) == {1}
        assert set(round_.accepted_slots(5)) == {0, 1}

    def test_wrong_slot_scores_zero(self):
        round_ = self._round([date(2020, 1, 1)], date(2020, 12, 1))
        round_.guess = 0

        assert round_.calculate_score({"tolerance_days": 0}) == 0

    def test_correct_property_reflects_score_delta(self):
        round_ = self._round([date(2020, 1, 1)], date(2020, 12, 1))
        assert round_.correct is None

        round_.guess = 1
        round_.score_delta = round_.calculate_score({"tolerance_days": 0})
        assert round_.correct is True

        round_.guess = 0
        round_.score_delta = round_.calculate_score({"tolerance_days": 0})
        assert round_.correct is False


class TestTimelineRoundTrip:
    def test_round_1_round_trips_with_its_seed_board(self):
        board = [CardSnapshot(id=uuid4(), date=date(2020, 1, 1))]
        card = CardSnapshot(id=uuid4(), date=date(2020, 3, 1))
        round_ = TimelineRound(id=uuid4(), game_id=uuid4(), round_index=1, board=board, card=card)
        round_.guess = 1
        round_.score_delta = 1

        payload = round_.to_payload()
        restored = TimelineRound.from_payload(
            round_.id, round_.game_id, round_.round_index, payload, round_.score_delta
        )

        assert restored.board == board
        assert restored.card == card
        assert restored.guess == 1
        assert restored.score_delta == 1

    def test_later_rounds_omit_the_board_from_their_payload(self):
        # Only round 1 persists a board; the rest are rebuilt at load time by
        # TimelineGame._hydrate_boards (TestTimelineBoardHydration below).
        board = [CardSnapshot(id=uuid4(), date=date(2020, 1, 1)), CardSnapshot(id=uuid4(), date=date(2020, 6, 1))]
        card = CardSnapshot(id=uuid4(), date=date(2020, 3, 1))
        round_ = TimelineRound(id=uuid4(), game_id=uuid4(), round_index=2, board=board, card=card)

        payload = round_.to_payload()

        assert "board" not in payload
        restored = TimelineRound.from_payload(round_.id, round_.game_id, round_.round_index, payload, None)
        assert restored.board == []
        assert restored.card == card

    def test_a_legacy_payload_with_a_board_still_restores_it(self):
        # Rows written before boards were slimmed carry one on every round - from_payload keeps
        # honoring it, which is the whole backward-compat story (no migration).
        board = [CardSnapshot(id=uuid4(), date=date(2020, 1, 1)), CardSnapshot(id=uuid4(), date=date(2020, 6, 1))]
        card = CardSnapshot(id=uuid4(), date=date(2020, 3, 1))
        legacy_payload = {
            "board": [c.to_dict() for c in board],
            "card": card.to_dict(),
            "guess": 1,
        }

        restored = TimelineRound.from_payload(uuid4(), uuid4(), 3, legacy_payload, 1)

        assert restored.board == board
        assert restored.card == card

    def test_round_trip_with_an_unanswered_round(self):
        board = [CardSnapshot(id=uuid4(), date=date(2020, 1, 1))]
        card = CardSnapshot(id=uuid4(), date=date(2020, 6, 1))
        round_ = TimelineRound(id=uuid4(), game_id=uuid4(), round_index=1, board=board, card=card)

        payload = round_.to_payload()
        restored = TimelineRound.from_payload(round_.id, round_.game_id, round_.round_index, payload, None)

        assert restored.guess is None
        assert restored.score_delta is None


def _replayed(game: TimelineGame, rounds_payloads: list[dict] | None = None) -> TimelineGame:
    """Round-trips a game the way GamesService does (to_payload rows -> from_payload -> the game
    constructor, see _row_to_game) - the path where boards omitted from payloads must come back."""
    payloads = rounds_payloads or [round_.to_payload() for round_ in game.rounds]
    rounds = [
        TimelineRound.from_payload(round_.id, round_.game_id, round_.round_index, payload, round_.score_delta)
        for round_, payload in zip(game.rounds, payloads, strict=True)
    ]
    return TimelineGame(id=game.id, rounds=rounds, content=_FiniteContent([]), score=game.score, finished=game.finished)


class TestTimelineBoardHydration:
    """Rounds >= 2 persist no board, so loading a game must rebuild every board (and the shown
    ids derived from them) exactly as they were when played."""

    def _played_game(self) -> TimelineGame:
        assets = [
            _asset(date(2020, 6, 1)),
            _asset(date(2020, 1, 1)),
            _asset(date(2020, 12, 1)),
            _asset(date(2020, 8, 1)),
        ]
        game = TimelineGame.start(id=uuid4(), content=_FiniteContent(assets))
        game.play_round(0)  # board=[Jun1], card=Jan1 -> slot 0
        game.play_round(2)  # board=[Jan1, Jun1], card=Dec1 -> slot 2; leaves round 3 pending
        return game

    def test_reloading_rebuilds_every_board_and_shown_ids(self):
        game = self._played_game()

        restored = _replayed(game)

        for original, loaded in zip(game.rounds, restored.rounds, strict=True):
            assert loaded.board == original.board
            assert loaded.card == original.card
            assert loaded.guess == original.guess
            assert loaded.shown_entities == original.shown_entities
        assert restored._shown_asset_ids == game._shown_asset_ids

    def test_a_mix_of_legacy_and_slim_payloads_reconstructs_the_same_boards(self):
        # A game saved before the slimming and resumed after it: old rounds still carry their
        # board (honored as-is), new rounds don't (rebuilt) - both shapes coexist in one game.
        game = self._played_game()
        payloads = [round_.to_payload() for round_ in game.rounds]
        payloads[1]["board"] = [c.to_dict() for c in game.rounds[1].board]  # round 2 as legacy

        restored = _replayed(game, payloads)

        for original, loaded in zip(game.rounds, restored.rounds, strict=True):
            assert loaded.board == original.board


class TestTimelineGame:
    def test_a_correct_guess_advances_the_game_and_draws_the_next_card(self):
        assets = [_asset(date(2020, 1, 1)), _asset(date(2020, 6, 1)), _asset(date(2020, 3, 1))]
        game = TimelineGame.start(id=uuid4(), content=_FiniteContent(assets))

        # round 1: board=[Jan1], card=Jun1 -> correct slot is 1 (after Jan1)
        game.play_round(1)

        assert game.finished is False
        assert game.score == 1
        assert len(game.rounds) == 2
        assert [c.date for c in game.rounds[1].board] == [date(2020, 1, 1), date(2020, 6, 1)]
        assert game.rounds[1].card.date == date(2020, 3, 1)

    def test_a_wrong_guess_ends_the_game(self):
        assets = [_asset(date(2020, 1, 1)), _asset(date(2020, 6, 1))]
        game = TimelineGame.start(id=uuid4(), content=_FiniteContent(assets))

        game.play_round(0)  # correct slot is 1, not 0

        assert game.finished is True
        assert game.score == 0
        assert len(game.rounds) == 1

    def test_correct_guess_inserts_the_previous_card_at_its_real_position(self):
        assets = [
            _asset(date(2020, 6, 1)),
            _asset(date(2020, 1, 1)),
            _asset(date(2020, 12, 1)),
            _asset(date(2020, 8, 1)),  # keeps the pool alive past round 2 - not itself asserted on
        ]
        game = TimelineGame.start(id=uuid4(), content=_FiniteContent(assets))

        # round 1: board=[Jun1], card=Jan1 -> correct slot is 0 (before Jun1)
        game.play_round(0)
        assert [c.date for c in game.rounds[1].board] == [date(2020, 1, 1), date(2020, 6, 1)]

        # round 2: board=[Jan1, Jun1], card=Dec1 -> correct slot is 2 (after Jun1)
        game.play_round(2)
        assert [c.date for c in game.rounds[2].board] == [
            date(2020, 1, 1),
            date(2020, 6, 1),
            date(2020, 12, 1),
        ]

    def test_playing_an_already_finished_game_raises(self):
        assets = [_asset(date(2020, 1, 1)), _asset(date(2020, 6, 1))]
        game = TimelineGame.start(id=uuid4(), content=_FiniteContent(assets))
        game.play_round(0)  # wrong -> finished
        assert game.finished is True

        with pytest.raises(ValueError):
            game.play_round(0)

    def test_pool_exhaustion_ends_the_game_as_a_perfect_run(self):
        assets = [
            _asset(date(2020, 1, 1)),
            _asset(date(2020, 6, 1)),
            _asset(date(2020, 3, 1)),
        ]
        game = TimelineGame.start(id=uuid4(), content=_FiniteContent(assets))

        game.play_round(1)  # correct: board=[Jan1], card=Jun1 -> slot 1
        assert game.finished is False

        game.play_round(1)  # correct: board=[Jan1, Jun1], card=Mar1 -> slot 1; pool now exhausted

        assert game.finished is True
        assert game.score == 2
        assert game.rounds[-1].correct is True


class TestTimelineAdminSettings:
    """Confirms an override actually changes live behavior, not just
    what GameSettingsService reports (see test_game_settings_service.py for that)."""

    def test_max_cards_ends_the_game_as_a_perfect_run(self):
        assets = [
            _asset(date(2020, 1, 1)),
            _asset(date(2020, 6, 1)),
            _asset(date(2020, 3, 1)),  # left unused - the cap kicks in before the pool would
        ]
        game = TimelineGame.start(id=uuid4(), content=_FiniteContent(assets), settings={"max_cards": 2})

        game.play_round(1)  # correct

        assert game.finished is True
        assert game.score == 1
        assert len(game.rounds) == 1
        assert game.rounds[-1].correct is True

    def test_tolerance_days_setting_changes_live_scoring(self):
        board = [CardSnapshot(id=uuid4(), date=date(2020, 1, 1)), CardSnapshot(id=uuid4(), date=date(2020, 1, 20))]
        card = CardSnapshot(id=uuid4(), date=date(2020, 1, 4))
        round_ = TimelineRound(id=uuid4(), game_id=uuid4(), round_index=1, board=board, card=card)
        round_.guess = 0

        assert round_.calculate_score({"tolerance_days": 0}) == 0
        assert round_.calculate_score({"tolerance_days": 5}) == 1
