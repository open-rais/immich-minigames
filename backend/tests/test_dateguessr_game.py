from datetime import date, timedelta
from uuid import uuid4

import pytest

from games.dateguessr import (
    DECAY_DAYS,
    MAX_SCORE,
    TOTAL_ROUNDS,
    AssetSnapshot,
    DateguessrGame,
    DateguessrRound,
)


def _guess_near(round_: DateguessrRound) -> date:
    return round_.asset.date


def _guess_far(round_: DateguessrRound) -> date:
    return round_.asset.date + timedelta(days=365 * 50)


class TestDateguessrGame:
    def test_has_five_rounds_then_finishes(self, immich_service):
        game = DateguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        rounds_played = 0
        while not game.finished and rounds_played < TOTAL_ROUNDS + 5:
            game.play_round(_guess_near(game.current_round))
            rounds_played += 1

        assert game.finished is True
        assert len(game.rounds) == TOTAL_ROUNDS
        assert rounds_played == TOTAL_ROUNDS

    def test_a_bad_guess_does_not_end_the_game_early(self, immich_service):
        game = DateguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        game.play_round(_guess_far(game.current_round))

        assert game.finished is False
        assert len(game.rounds) == 2

    def test_does_not_repeat_a_shown_asset_within_the_same_game(self, immich_service):
        game = DateguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        shown = [game.current_round.asset.id]

        while not game.finished:
            game.play_round(_guess_near(game.current_round))
            if game.finished:
                break
            new_id = game.current_round.asset.id
            assert new_id not in shown
            shown.append(new_id)

    def test_playing_an_already_finished_game_raises(self, immich_service):
        game = DateguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        while not game.finished:
            game.play_round(_guess_near(game.current_round))

        with pytest.raises(ValueError):
            game.play_round(date(2020, 1, 1))


class TestDateguessrScoring:
    """Isolated from the DB - constructs rounds directly against known dates."""

    def _round_at(self, d: date) -> DateguessrRound:
        asset = AssetSnapshot(id=uuid4(), date=d)
        return DateguessrRound(id=uuid4(), game_id=uuid4(), round_index=1, asset=asset)

    def test_exact_day_match_gives_max_score(self):
        round_ = self._round_at(date(2020, 6, 15))
        round_.guess = date(2020, 6, 15)

        assert round_.days_off == 0
        assert round_.calculate_score() == MAX_SCORE

    def test_score_decays_with_days_off(self):
        near = self._round_at(date(2020, 1, 1))
        near.guess = date(2020, 1, 8)

        far = self._round_at(date(2020, 1, 1))
        far.guess = date(2015, 1, 1)

        assert near.calculate_score() > far.calculate_score()

    def test_score_at_the_decay_scale_matches_the_formula(self):
        round_ = self._round_at(date(2020, 1, 1))
        round_.guess = date(2020, 1, 1) + timedelta(days=round(DECAY_DAYS))

        # score = round(MAX_SCORE * exp(-days_off / DECAY_DAYS)) ~= MAX_SCORE / e at days_off == DECAY_DAYS
        assert abs(round_.calculate_score() - MAX_SCORE / 2.71828) < 50

    def test_score_floors_at_zero_for_a_far_guess(self):
        round_ = self._round_at(date(2020, 1, 1))
        round_.guess = date(1900, 1, 1)

        assert round_.calculate_score() == 0
