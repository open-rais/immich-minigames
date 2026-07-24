from uuid import uuid4

import pytest

from games.whos_that_person import HiddenFace, IncompleteGuessError, WhosThatPersonGame, WhosThatPersonRound


def _correct_guess(round_: WhosThatPersonRound) -> dict:
    return {face.face_id: face.person_id for face in round_.faces}


def _play_correctly_to_completion(game: WhosThatPersonGame) -> None:
    while not game.finished:
        game.play_round(_correct_guess(game.current_round))


class TestWhosThatPersonGame:
    def test_starts_with_one_to_five_pending_faces(self, immich_service):
        game = WhosThatPersonGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        assert game.finished is False
        assert len(game.rounds) == 1
        assert 1 <= len(game.current_round.faces) <= 5
        assert game.current_round.answered is False
        assert all(face.person_name for face in game.current_round.faces)

    def test_correct_guess_reveals_answers_and_scores_the_streak(self, immich_service):
        game = WhosThatPersonGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        first_round = game.current_round
        n = len(first_round.faces)

        result = game.play_round(_correct_guess(first_round))

        assert result.score_delta == sum(range(1, n + 1))
        assert result.score == result.score_delta
        assert first_round.correct is True
        assert first_round.ending_streak == n

    def test_wrong_guess_scores_less_and_does_not_end_the_game(self, immich_service):
        # A single round's faces never reach the 15-person budget on their own (max 5 < 15), so a
        # wrong guess here should never finish the game - unlike MoreOrLess, correctness doesn't
        # gate has_next_round() at all for this game.
        game = WhosThatPersonGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        first_round = game.current_round
        guess = _correct_guess(first_round)
        [some_face] = first_round.faces[:1]
        guess[some_face.face_id] = uuid4()  # deliberately wrong

        result = game.play_round(guess)

        assert first_round.correct is False
        assert result.score_delta < sum(range(1, len(first_round.faces) + 1))
        assert result.finished is False

    def test_incomplete_guess_raises(self, immich_service):
        game = WhosThatPersonGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        guess = _correct_guess(game.current_round)
        guess.popitem()

        with pytest.raises(IncompleteGuessError):
            game.play_round(guess)

    def test_guess_with_an_extra_unknown_face_id_raises(self, immich_service):
        game = WhosThatPersonGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        guess = _correct_guess(game.current_round)
        guess[uuid4()] = uuid4()

        with pytest.raises(IncompleteGuessError):
            game.play_round(guess)

    def test_game_ends_after_exactly_15_people_asked(self, immich_service):
        game = WhosThatPersonGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        _play_correctly_to_completion(game)

        assert game.finished is True
        assert sum(len(r.faces) for r in game.rounds) == 15

    def test_never_repeats_a_photo_within_a_game(self, immich_service):
        game = WhosThatPersonGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        _play_correctly_to_completion(game)

        asset_ids = [r.asset_id for r in game.rounds]
        assert len(asset_ids) == len(set(asset_ids))

    def test_playing_an_already_finished_game_raises(self, immich_service):
        game = WhosThatPersonGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        _play_correctly_to_completion(game)

        with pytest.raises(ValueError):
            game.play_round({})


class TestWhosThatPersonAdminSettings:
    """ADMIN-FEATURE.md point #4 - confirms an override actually changes live behavior, not just
    what GameSettingsService reports (see test_game_settings_service.py for that)."""

    def test_total_people_override_changes_how_many_are_asked(self, immich_service):
        game = WhosThatPersonGame.start(
            id=uuid4(), owner="owner", immich_service=immich_service, settings={"total_people": 3}
        )

        _play_correctly_to_completion(game)

        assert game.finished is True
        assert sum(len(r.faces) for r in game.rounds) == 3


class TestWhosThatPersonRoundScoring:
    """Isolated from the DB - constructs rounds/faces directly to deterministically exercise the
    streak math, same style as test_more_or_less_game.py's TestMoreOrLessRoundTieScoring."""

    def _face(self) -> HiddenFace:
        return HiddenFace(
            face_id=uuid4(),
            person_id=uuid4(),
            person_name="Someone",
            image_width=100,
            image_height=100,
            bounding_box_x1=0,
            bounding_box_y1=0,
            bounding_box_x2=10,
            bounding_box_y2=10,
        )

    def _round(self, correctness: list[bool], incoming_streak: int = 0) -> WhosThatPersonRound:
        faces = [self._face() for _ in correctness]
        guess = {face.face_id: (face.person_id if is_correct else uuid4()) for face, is_correct in zip(faces, correctness)}
        round_ = WhosThatPersonRound(
            id=uuid4(), game_id=uuid4(), round_index=1, asset_id=uuid4(), faces=faces, incoming_streak=incoming_streak
        )
        round_.guess = guess
        return round_

    def test_all_correct_advances_streak_by_face_count(self):
        round_ = self._round([True, True, True])

        assert round_.calculate_score() == 1 + 2 + 3
        assert round_.ending_streak == 3

    def test_all_correct_continues_the_incoming_streak(self):
        round_ = self._round([True, True], incoming_streak=2)

        assert round_.calculate_score() == 3 + 4
        assert round_.ending_streak == 4

    def test_any_miss_resets_the_streak_before_scoring_the_rounds_own_hits(self):
        # Incoming streak of 5 is discarded entirely because this round contains a miss - the two
        # hits only get to build a *new* streak from 0, not extend the incoming one.
        round_ = self._round([True, False, True], incoming_streak=5)

        assert round_.calculate_score() == 1 + 0 + 1
        assert round_.ending_streak == 1

    def test_worked_example_from_design_doc_as_one_grouped_round(self):
        # docs/GAMES/WHOS_THAT_PERSON.md's worked example (correct-correct-correct-wrong-correct-
        # correct across 6 separate rounds -> +1,+2,+3,+0,+1,+2 = 9), reinterpreted as one round
        # covering all 6 faces. The total matches because a round that starts with no incoming
        # streak resets to 0 at the miss either way.
        round_ = self._round([True, True, True, False, True, True])

        assert round_.calculate_score() == 1 + 2 + 3 + 0 + 1 + 2
        assert round_.ending_streak == 2

    def test_all_wrong_scores_zero_and_resets(self):
        round_ = self._round([False, False], incoming_streak=4)

        assert round_.calculate_score() == 0
        assert round_.ending_streak == 0

    def test_correct_property_reflects_every_face(self):
        all_correct = self._round([True, True])
        some_wrong = self._round([True, False])
        all_correct.calculate_score()
        some_wrong.calculate_score()

        assert all_correct.correct is True
        assert some_wrong.correct is False

    def test_correct_property_is_none_until_answered(self):
        round_ = WhosThatPersonRound(
            id=uuid4(), game_id=uuid4(), round_index=1, asset_id=uuid4(), faces=[self._face()]
        )

        assert round_.correct is None
