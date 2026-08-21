from uuid import uuid4

import pytest

from games.trivium import Answer, GeneratedQuestion, TriviumGame, TriviumRound
from games.trivium.questions.base import MediaSpec


def _question(subject_id=None, correct_index=0, alternatives=None, question_kind="test_kind") -> GeneratedQuestion:
    return GeneratedQuestion(
        question_kind=question_kind,
        subject_id=subject_id or uuid4(),
        params={"person_id": "irrelevant"},
        alternatives=alternatives or [2000, 2001, 2002, 2003],
        correct_index=correct_index,
        media=MediaSpec(),
    )


def _round(question: GeneratedQuestion | None = None) -> TriviumRound:
    return TriviumRound.of(id=uuid4(), game_id=uuid4(), round_index=1, question=question or _question())


class _FiniteQuestionType:
    """Deterministic QuestionType test double - plays back a fixed list of GeneratedQuestions in
    order (skipping any whose subject is already excluded), so game-flow tests don't depend on
    real Immich data. Mirrors games/timeline/tests' _FiniteContent."""

    def __init__(self, questions: list[GeneratedQuestion]) -> None:
        self._questions = list(questions)
        self._next = 0

    def can_generate(self, immich_service, exclude_subject_ids) -> bool:
        return any(q.subject_id not in exclude_subject_ids for q in self._questions[self._next :])

    def generate(self, immich_service, exclude_subject_ids) -> GeneratedQuestion:
        while self._questions[self._next].subject_id in exclude_subject_ids:
            self._next += 1
        question = self._questions[self._next]
        self._next += 1
        return question


def _start_game(questions: list[GeneratedQuestion], settings: dict[str, float] | None = None) -> TriviumGame:
    return TriviumGame.start(
        id=uuid4(),
        mode="birthday",
        immich_service=None,
        question_types=[_FiniteQuestionType(questions)],
        settings=settings,
    )


class TestTriviumRoundScoring:
    """Isolated from the DB - constructs rounds directly against a known question."""

    def test_instant_answer_scores_max_points(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=1, elapsed_ms=0)
        assert round_.calculate_score({"max_points": 100, "answer_time_seconds": 10}) == 100

    def test_half_the_time_scores_half(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=1, elapsed_ms=5000)
        assert round_.calculate_score({"max_points": 100, "answer_time_seconds": 10}) == 50

    def test_negative_elapsed_is_clamped_to_instant(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=1, elapsed_ms=-500)
        assert round_.calculate_score({"max_points": 100, "answer_time_seconds": 10}) == 100

    def test_elapsed_past_the_limit_is_clamped_to_zero(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=1, elapsed_ms=999_999)
        assert round_.calculate_score({"max_points": 100, "answer_time_seconds": 10}) == 0

    def test_wrong_alternative_scores_zero_regardless_of_elapsed(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=0, elapsed_ms=0)
        assert round_.calculate_score({"max_points": 100, "answer_time_seconds": 10}) == 0

    def test_timeout_null_alternative_scores_zero(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=None, elapsed_ms=10_000)
        assert round_.calculate_score({"max_points": 100, "answer_time_seconds": 10}) == 0

    def test_missing_settings_fall_back_to_module_defaults(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=1, elapsed_ms=0)
        assert round_.calculate_score(None) == 100
        assert round_.calculate_score({}) == 100

    def test_correct_property_is_independent_of_score_delta(self):
        # A correct answer given right at the time limit still scores 0 points - TRIVIUM.md §3 -
        # but is still a *win* for has_next_round()'s purposes, not a loss.
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=1, elapsed_ms=10_000)
        round_.score_delta = round_.calculate_score({"max_points": 100, "answer_time_seconds": 10})

        assert round_.score_delta == 0
        assert round_.correct is True

    def test_correct_is_none_before_answering(self):
        assert _round().correct is None

    def test_wrong_alternative_is_not_correct(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=0, elapsed_ms=0)
        assert round_.correct is False

    def test_timeout_is_not_correct(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=None, elapsed_ms=10_000)
        assert round_.correct is False


class TestTriviumRoundTrip:
    def test_unanswered_round_round_trips(self):
        question = _question(correct_index=2, alternatives=[1990, 1991, 1992, 1993])
        round_ = _round(question)

        payload = round_.to_payload()
        restored = TriviumRound.from_payload(round_.id, round_.game_id, round_.round_index, payload, None)

        assert restored.question_kind == question.question_kind
        assert restored.subject_id == question.subject_id
        assert restored.params == question.params
        assert restored.alternatives == question.alternatives
        assert restored.correct_index == question.correct_index
        assert restored.media == question.media
        assert restored.guess is None
        assert restored.score_delta is None
        assert restored.shown_entities == [question.subject_id]

    def test_answered_round_round_trips(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=1, elapsed_ms=1234)
        round_.score_delta = round_.calculate_score({"max_points": 100, "answer_time_seconds": 10})

        payload = round_.to_payload()
        restored = TriviumRound.from_payload(round_.id, round_.game_id, round_.round_index, payload, round_.score_delta)

        assert restored.guess == Answer(alternative=1, elapsed_ms=1234)
        assert restored.score_delta == round_.score_delta

    def test_timeout_guess_round_trips_with_a_null_alternative(self):
        round_ = _round(_question(correct_index=1))
        round_.guess = Answer(alternative=None, elapsed_ms=10_000)
        round_.score_delta = 0

        payload = round_.to_payload()
        restored = TriviumRound.from_payload(round_.id, round_.game_id, round_.round_index, payload, 0)

        assert restored.guess == Answer(alternative=None, elapsed_ms=10_000)

    def test_media_with_ids_round_trips(self):
        asset_id, person_id = uuid4(), uuid4()
        person_ids = [uuid4(), uuid4()]
        media = MediaSpec(kind="person_thumbnails", asset_id=asset_id, person_id=person_id, person_ids=person_ids)
        round_ = _round(_question())
        round_.media = media

        payload = round_.to_payload()
        restored = TriviumRound.from_payload(round_.id, round_.game_id, round_.round_index, payload, None)

        assert restored.media == media


class TestTriviumGame:
    def test_correct_guess_chains_a_new_round(self):
        game = _start_game([_question(correct_index=1), _question(correct_index=0)])
        first_round = game.current_round

        result = game.play_round(Answer(alternative=1, elapsed_ms=0))

        assert result.score_delta == 100
        assert result.score == 100
        assert result.finished is False
        assert len(game.rounds) == 2
        assert game.current_round is not first_round

    def test_wrong_guess_ends_the_game(self):
        game = _start_game([_question(correct_index=1), _question(correct_index=0)])

        result = game.play_round(Answer(alternative=0, elapsed_ms=0))

        assert result.score_delta == 0
        assert result.score == 0
        assert result.finished is True
        assert len(game.rounds) == 1

    def test_timeout_ends_the_game(self):
        game = _start_game([_question(correct_index=1), _question(correct_index=0)])

        result = game.play_round(Answer(alternative=None, elapsed_ms=10_000))

        assert result.finished is True
        assert result.score == 0

    def test_playing_an_already_finished_game_raises(self):
        game = _start_game([_question(correct_index=1)])
        game.play_round(Answer(alternative=0, elapsed_ms=0))  # wrong -> finished
        assert game.finished is True

        with pytest.raises(ValueError):
            game.play_round(Answer(alternative=0, elapsed_ms=0))

    def test_a_subject_never_repeats_within_the_same_game(self):
        subject = uuid4()
        # Both questions share the same subject - the pool is exhausted after round 1 since
        # TriviumGame excludes every subject already shown, permanently (TRIVIUM.md §7).
        game = _start_game([_question(subject_id=subject, correct_index=1)] * 2)

        result = game.play_round(Answer(alternative=1, elapsed_ms=0))

        assert result.finished is True
        assert result.score == 100
        assert game.rounds[-1].correct is True

    def test_pool_exhaustion_ends_the_game_as_a_perfect_run(self):
        game = _start_game([_question(correct_index=1), _question(correct_index=0)])

        game.play_round(Answer(alternative=1, elapsed_ms=0))  # correct, no more content left
        assert game.finished is False

        game.play_round(Answer(alternative=game.current_round.correct_index, elapsed_ms=0))

        assert game.finished is True
        assert game.score == 200
        assert game.rounds[-1].correct is True


class TestTriviumAdminSettings:
    def test_max_rounds_ends_the_game_as_a_perfect_run(self):
        game = _start_game(
            [_question(correct_index=1), _question(correct_index=0), _question(correct_index=0)],
            settings={"max_rounds": 1},
        )

        result = game.play_round(Answer(alternative=1, elapsed_ms=0))

        assert result.finished is True
        assert result.score == 100
        assert len(game.rounds) == 1
        assert game.rounds[-1].correct is True

    def test_max_rounds_zero_means_no_limit(self):
        game = _start_game(
            [_question(correct_index=1), _question(correct_index=0)],
            settings={"max_rounds": 0},
        )

        result = game.play_round(Answer(alternative=1, elapsed_ms=0))

        assert result.finished is False
        assert len(game.rounds) == 2

    def test_max_points_and_answer_time_settings_change_live_scoring(self):
        game = _start_game(
            [_question(correct_index=1), _question(correct_index=0)],
            settings={"max_points": 50, "answer_time_seconds": 20},
        )

        result = game.play_round(Answer(alternative=1, elapsed_ms=10_000))  # half of 20s

        assert result.score_delta == 25
