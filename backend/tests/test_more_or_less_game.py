from uuid import uuid4

import pytest

from games.more_or_less import _RECENT_EXCLUDE_WINDOW, MoreOrLessGame, MoreOrLessRound, PersonSnapshot


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
        # A tie can't be scored "wrong" either way (see MoreOrLessRound.calculate_score), so
        # _wrong_guess() only actually loses the round when the two aren't tied - guard the
        # assertion instead of assuming a loss, so this test isn't flaky on the rare tie.
        tied = first_round.candidate.asset_count == first_round.reference.asset_count

        result = game.play_round(_wrong_guess(first_round))

        if tied:
            assert result.score_delta == 1
            assert result.finished is False
        else:
            assert result.score_delta == 0
            assert result.score == 0
            assert result.finished is True
            assert len(game.rounds) == 1

    def test_does_not_repeat_a_recently_shown_candidate(self, immich_service):
        # A correct guess intentionally carries the just-revealed candidate over as the next
        # round's reference (that's the streak mechanic) - what must not repeat is a brand new
        # *candidate* that was already shown within the last _RECENT_EXCLUDE_WINDOW people (the
        # game is infinite - see test_game_continues_past_the_full_named_people_pool below - so
        # repeats are expected once a person ages out of that window, just not before).
        game = MoreOrLessGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        recent = [game.current_round.reference.id, game.current_round.candidate.id]
        for _ in range(_RECENT_EXCLUDE_WINDOW + 3):
            if game.finished:
                break
            game.play_round(_correct_guess(game.current_round))
            if game.finished:
                break
            new_candidate_id = game.current_round.candidate.id
            window = recent[-_RECENT_EXCLUDE_WINDOW:]
            assert new_candidate_id not in window, "repeated a candidate still within the recent-exclude window"
            recent.append(new_candidate_id)

    def test_game_continues_past_the_full_named_people_pool(self, immich_service):
        # The game must not end just because every named person has been shown once - it's
        # infinite, only avoiding *recent* repeats (_RECENT_EXCLUDE_WINDOW), not all-time ones.
        named_people_count = len(immich_service.get_persons(named_only=True, limit=1000))

        game = MoreOrLessGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        for _ in range(named_people_count + 5):
            if game.finished:
                break
            game.play_round(_correct_guess(game.current_round))

        assert not game.finished, "game ended after cycling the full named-people pool instead of continuing"
        assert len(game.rounds) > named_people_count

    def test_playing_an_already_finished_game_raises(self, immich_service):
        game = MoreOrLessGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        game.play_round(_wrong_guess(game.current_round))

        with pytest.raises(ValueError):
            game.play_round("more")

    def test_starting_with_no_named_people_raises_a_friendly_error(self, immich_service, monkeypatch):
        # Regression test: get_persons(..., limit=1) can return [] (empty library), and
        # `[reference] = ...` used to raise a bare `ValueError: not enough values to unpack`
        # instead of ever reaching this friendly message.
        monkeypatch.setattr(immich_service, "get_persons", lambda **kwargs: [])

        with pytest.raises(ValueError, match="not enough named people"):
            MoreOrLessGame.start(id=uuid4(), owner="owner", immich_service=immich_service)


class TestMoreOrLessRoundTieScoring:
    """Isolated from the DB - constructs rounds directly to deterministically exercise a tie,
    which is rare (and not reliably reproducible) via the real random-candidate-picking flow."""

    def _tied_round(self, guess: str) -> MoreOrLessRound:
        reference = PersonSnapshot(id=uuid4(), name="Reference", asset_count=42)
        candidate = PersonSnapshot(id=uuid4(), name="Candidate", asset_count=42)
        round_ = MoreOrLessRound(id=uuid4(), game_id=uuid4(), round_index=1, reference=reference, candidate=candidate)
        round_.guess = guess
        return round_

    def test_tie_scores_a_win_when_guess_is_more(self):
        assert self._tied_round("more").calculate_score() == 1

    def test_tie_scores_a_win_when_guess_is_less(self):
        assert self._tied_round("less").calculate_score() == 1
