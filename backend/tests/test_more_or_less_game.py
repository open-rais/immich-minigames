from uuid import uuid4

import pytest

from games.more_or_less import MoreOrLessGame


def _wrong_guess(round_) -> str:
    return "less" if round_.candidate.asset_count > round_.reference.asset_count else "more"


def _correct_guess(round_) -> str:
    return "more" if round_.candidate.asset_count > round_.reference.asset_count else "less"


class TestMoreOrLessGame:
    def test_correct_guess_chains_a_new_round_and_scores_one(self, immich_service):
        game = MoreOrLessGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        first_round = game.current_round

        result = game.play_round(_correct_guess(first_round))

        assert result.score_delta == 1
        assert result.score == 1
        assert result.finished is False
        assert len(game.rounds) == 2
        assert game.current_round is not first_round

    def test_wrong_guess_ends_the_game_and_scores_zero(self, immich_service):
        game = MoreOrLessGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        first_round = game.current_round

        result = game.play_round(_wrong_guess(first_round))

        assert result.score_delta == 0
        assert result.score == 0
        assert result.finished is True
        assert len(game.rounds) == 1

    def test_never_repeats_a_candidate_within_the_same_game(self, immich_service):
        # A correct guess intentionally carries the just-revealed candidate over as the next
        # round's reference (that's the streak mechanic) - what must never repeat is which person
        # gets introduced as a brand new *candidate*.
        game = MoreOrLessGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        seen_candidate_ids = {game.current_round.reference.id, game.current_round.candidate.id}
        for _ in range(10):
            if game.finished:
                break
            game.play_round(_correct_guess(game.current_round))
            if game.finished:
                break
            new_candidate_id = game.current_round.candidate.id
            assert new_candidate_id not in seen_candidate_ids, "a candidate repeated within the same game"
            seen_candidate_ids.add(new_candidate_id)

    def test_playing_an_already_finished_game_raises(self, immich_service):
        game = MoreOrLessGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        game.play_round(_wrong_guess(game.current_round))

        with pytest.raises(ValueError):
            game.play_round("more")
