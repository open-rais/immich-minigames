from datetime import date
from uuid import UUID, uuid4

import pytest

from games.immichdle import (
    ASSET_COUNT_WEIGHT_EXPONENT,
    DuplicateGuessError,
    ImmichdleGame,
    InvalidGuessError,
    PersonSnapshot,
    _compute_clues,
)


def _wrong_person_id(immich_service, game: ImmichdleGame) -> UUID:
    [candidate] = immich_service.get_persons(named_only=True, limit=1, exclude_ids=frozenset({game.target.id}))
    return candidate.id


class TestImmichdleGame:
    def test_starts_with_score_100_and_one_pending_round(self, immich_service):
        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        assert game.score == 100
        assert game.finished is False
        assert len(game.rounds) == 1
        assert game.current_round.answered is False

    def test_correct_guess_wins_without_losing_points(self, immich_service):
        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        result = game.play_round(game.target.id)

        assert result.score_delta == 0
        assert result.score == 100
        assert result.finished is True
        assert game.rounds[-1].correct is True

    def test_wrong_guess_subtracts_five_and_continues(self, immich_service):
        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        wrong_id = _wrong_person_id(immich_service, game)

        result = game.play_round(wrong_id)

        assert result.score_delta == -5
        assert result.score == 95
        assert result.finished is False
        assert len(game.rounds) == 2
        assert game.rounds[0].correct is False
        assert game.rounds[0].guessed_person is not None
        assert game.rounds[0].clues is not None

    def test_correct_guess_gives_a_sane_assets_together_count(self, immich_service):
        """Guarding against a self-join bug in get_assets_together_count(id, id): guessing the
        target itself should count photos where the target's own face is tagged, not 0/blow up."""
        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        game.play_round(game.target.id)

        assert game.rounds[-1].clues.assets_together > 0

    def test_score_floors_at_zero_and_ends_the_game(self, immich_service):
        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        wrong_candidates = immich_service.get_persons(
            named_only=True, limit=28, exclude_ids=frozenset({game.target.id})
        )
        assert len(wrong_candidates) >= 20, "dev data needs at least ~20 named people besides the target"

        for candidate in wrong_candidates:
            if game.finished:
                break
            game.play_round(candidate.id)

        assert game.finished is True
        assert game.score == 0

    def test_duplicate_guess_raises(self, immich_service):
        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        wrong_id = _wrong_person_id(immich_service, game)
        game.play_round(wrong_id)

        with pytest.raises(DuplicateGuessError):
            game.play_round(wrong_id)

    def test_invalid_person_id_raises(self, immich_service):
        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        with pytest.raises(InvalidGuessError):
            game.play_round(uuid4())

    def test_playing_an_already_finished_game_raises(self, immich_service):
        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        game.play_round(game.target.id)

        with pytest.raises(ValueError):
            game.play_round(game.target.id)

    def test_starting_with_no_named_people_raises_a_friendly_error(self, immich_service, monkeypatch):
        # Regression test: get_persons(..., limit=1) can return [] (empty library), and
        # `[target_person] = ...` used to raise a bare `ValueError: not enough values to unpack`
        # instead of ever reaching this friendly message.
        monkeypatch.setattr(immich_service, "get_persons", lambda **kwargs: [])

        with pytest.raises(ValueError, match="not enough named people"):
            ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)


class TestImmichdleAdminSettings:
    """ADMIN-FEATURE.md point #4 - confirms an override actually changes live behavior, not just
    what GameSettingsService reports (see test_game_settings_service.py for that)."""

    def test_starting_score_override_changes_the_initial_score(self, immich_service):
        game = ImmichdleGame.start(
            id=uuid4(), owner="owner", immich_service=immich_service, settings={"starting_score": 50}
        )

        assert game.score == 50

    def test_wrong_guess_penalty_override_changes_the_score_delta(self, immich_service):
        game = ImmichdleGame.start(
            id=uuid4(), owner="owner", immich_service=immich_service, settings={"wrong_guess_penalty": 20}
        )
        wrong_id = _wrong_person_id(immich_service, game)

        result = game.play_round(wrong_id)

        assert result.score_delta == -20

    def _spy_on_target_selection_call(self, immich_service, monkeypatch) -> list[dict]:
        """Records only the kwargs of the `random=True` call (target selection) - start() makes a
        second, unrelated get_persons() call right after (the has_alternative check) that doesn't
        take asset_count_weight, so capturing every call indiscriminately would overwrite it."""
        calls: list[dict] = []
        real_get_persons = immich_service.get_persons

        def _spy(**kwargs):
            if kwargs.get("random"):
                calls.append(kwargs)
            return real_get_persons(**kwargs)

        monkeypatch.setattr(immich_service, "get_persons", _spy)
        return calls

    def test_asset_count_weight_override_is_forwarded_to_target_selection(self, immich_service, monkeypatch):
        calls = self._spy_on_target_selection_call(immich_service, monkeypatch)

        ImmichdleGame.start(
            id=uuid4(), owner="owner", immich_service=immich_service, settings={"asset_count_weight": 0.7}
        )

        assert calls[0]["asset_count_weight"] == 0.7

    def test_asset_count_weight_defaults_when_not_overridden(self, immich_service, monkeypatch):
        calls = self._spy_on_target_selection_call(immich_service, monkeypatch)

        ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        assert calls[0]["asset_count_weight"] == ASSET_COUNT_WEIGHT_EXPONENT


class TestComputeClues:
    """Isolated from the DB - constructs snapshots directly to deterministically exercise every
    clue direction, same style as test_more_or_less_game.py's TestMoreOrLessRoundTieScoring."""

    def _snapshot(self, *, name: str, asset_count: int, birth_date: date | None, first_asset_date: date | None) -> PersonSnapshot:
        return PersonSnapshot(
            id=uuid4(), name=name, asset_count=asset_count, birth_date=birth_date, first_asset_date=first_asset_date
        )

    def test_age_older_younger_same_unknown(self):
        target = self._snapshot(name="Target", asset_count=1, birth_date=date(1990, 1, 1), first_asset_date=None)
        older = self._snapshot(name="Older", asset_count=1, birth_date=date(1980, 1, 1), first_asset_date=None)
        younger = self._snapshot(name="Younger", asset_count=1, birth_date=date(2000, 1, 1), first_asset_date=None)
        same = self._snapshot(name="Same", asset_count=1, birth_date=date(1990, 1, 1), first_asset_date=None)
        unknown = self._snapshot(name="Unknown", asset_count=1, birth_date=None, first_asset_date=None)

        assert _compute_clues(target, older, None, 0).age == "older"
        assert _compute_clues(target, younger, None, 0).age == "younger"
        assert _compute_clues(target, same, None, 0).age == "same"
        assert _compute_clues(target, unknown, None, 0).age == "unknown"

    def test_age_close_bucket(self):
        target = self._snapshot(name="Target", asset_count=1, birth_date=date(1990, 6, 1), first_asset_date=None)
        close = self._snapshot(name="Close", asset_count=1, birth_date=date(1990, 1, 1), first_asset_date=None)
        far = self._snapshot(name="Far", asset_count=1, birth_date=date(1980, 1, 1), first_asset_date=None)
        same = self._snapshot(name="Same", asset_count=1, birth_date=date(1990, 6, 1), first_asset_date=None)
        unknown = self._snapshot(name="Unknown", asset_count=1, birth_date=None, first_asset_date=None)

        assert _compute_clues(target, close, None, 0).age_close is True
        assert _compute_clues(target, far, None, 0).age_close is False
        assert _compute_clues(target, same, None, 0).age_close is None
        assert _compute_clues(target, unknown, None, 0).age_close is None

    def test_age_both_unknown_distinguishes_from_one_unknown(self):
        known_target = self._snapshot(name="Target", asset_count=1, birth_date=date(1990, 1, 1), first_asset_date=None)
        unknown_target = self._snapshot(name="Target", asset_count=1, birth_date=None, first_asset_date=None)
        known_guess = self._snapshot(name="Guess", asset_count=1, birth_date=date(1990, 1, 1), first_asset_date=None)
        unknown_guess = self._snapshot(name="Guess", asset_count=1, birth_date=None, first_asset_date=None)

        assert _compute_clues(unknown_target, unknown_guess, None, 0).age_both_unknown is True
        assert _compute_clues(known_target, unknown_guess, None, 0).age_both_unknown is False
        assert _compute_clues(unknown_target, known_guess, None, 0).age_both_unknown is False
        assert _compute_clues(known_target, known_guess, None, 0).age_both_unknown is False

    def test_asset_count_more_less_equal(self):
        target = self._snapshot(name="Target", asset_count=10, birth_date=None, first_asset_date=None)
        more = self._snapshot(name="More", asset_count=20, birth_date=None, first_asset_date=None)
        less = self._snapshot(name="Less", asset_count=5, birth_date=None, first_asset_date=None)
        equal = self._snapshot(name="Equal", asset_count=10, birth_date=None, first_asset_date=None)

        assert _compute_clues(target, more, None, 0).asset_count == "more"
        assert _compute_clues(target, less, None, 0).asset_count == "less"
        assert _compute_clues(target, equal, None, 0).asset_count == "equal"

    def test_asset_count_close_bucket(self):
        target = self._snapshot(name="Target", asset_count=100, birth_date=None, first_asset_date=None)
        close = self._snapshot(name="Close", asset_count=150, birth_date=None, first_asset_date=None)
        far = self._snapshot(name="Far", asset_count=300, birth_date=None, first_asset_date=None)
        equal = self._snapshot(name="Equal", asset_count=100, birth_date=None, first_asset_date=None)

        assert _compute_clues(target, close, None, 0).asset_count_close is True
        assert _compute_clues(target, far, None, 0).asset_count_close is False
        assert _compute_clues(target, equal, None, 0).asset_count_close is None

    def test_first_appearance_before_after_same_unknown(self):
        target = self._snapshot(name="Target", asset_count=1, birth_date=None, first_asset_date=date(2015, 6, 1))
        before = self._snapshot(name="Before", asset_count=1, birth_date=None, first_asset_date=date(2010, 1, 1))
        after = self._snapshot(name="After", asset_count=1, birth_date=None, first_asset_date=date(2020, 1, 1))
        same = self._snapshot(name="Same", asset_count=1, birth_date=None, first_asset_date=date(2015, 6, 1))
        unknown = self._snapshot(name="Unknown", asset_count=1, birth_date=None, first_asset_date=None)

        assert _compute_clues(target, before, None, 0).first_appearance == "before"
        assert _compute_clues(target, after, None, 0).first_appearance == "after"
        assert _compute_clues(target, same, None, 0).first_appearance == "same"
        assert _compute_clues(target, unknown, None, 0).first_appearance == "unknown"

    def test_first_appearance_close_bucket(self):
        target = self._snapshot(name="Target", asset_count=1, birth_date=None, first_asset_date=date(2015, 6, 1))
        close = self._snapshot(name="Close", asset_count=1, birth_date=None, first_asset_date=date(2015, 1, 1))
        far = self._snapshot(name="Far", asset_count=1, birth_date=None, first_asset_date=date(2010, 1, 1))
        same = self._snapshot(name="Same", asset_count=1, birth_date=None, first_asset_date=date(2015, 6, 1))
        unknown = self._snapshot(name="Unknown", asset_count=1, birth_date=None, first_asset_date=None)

        assert _compute_clues(target, close, None, 0).first_appearance_close is True
        assert _compute_clues(target, far, None, 0).first_appearance_close is False
        assert _compute_clues(target, same, None, 0).first_appearance_close is None
        assert _compute_clues(target, unknown, None, 0).first_appearance_close is None

    def test_first_appearance_both_unknown_distinguishes_from_one_unknown(self):
        known_target = self._snapshot(name="Target", asset_count=1, birth_date=None, first_asset_date=date(2015, 6, 1))
        unknown_target = self._snapshot(name="Target", asset_count=1, birth_date=None, first_asset_date=None)
        known_guess = self._snapshot(name="Guess", asset_count=1, birth_date=None, first_asset_date=date(2015, 6, 1))
        unknown_guess = self._snapshot(name="Guess", asset_count=1, birth_date=None, first_asset_date=None)

        assert _compute_clues(unknown_target, unknown_guess, None, 0).first_appearance_both_unknown is True
        assert _compute_clues(known_target, unknown_guess, None, 0).first_appearance_both_unknown is False
        assert _compute_clues(unknown_target, known_guess, None, 0).first_appearance_both_unknown is False
        assert _compute_clues(known_target, known_guess, None, 0).first_appearance_both_unknown is False

    def test_common_names_counts_shared_tokens_case_insensitively(self):
        target = self._snapshot(name="Ana Maria Perez", asset_count=1, birth_date=None, first_asset_date=None)
        guess = self._snapshot(name="ana Gomez", asset_count=1, birth_date=None, first_asset_date=None)
        stranger = self._snapshot(name="Jose Rojas", asset_count=1, birth_date=None, first_asset_date=None)

        assert _compute_clues(target, guess, None, 0).common_names == 1
        assert _compute_clues(target, stranger, None, 0).common_names == 0

    def test_ml_similarity_and_assets_together_pass_through_unchanged(self):
        target = self._snapshot(name="Target", asset_count=1, birth_date=None, first_asset_date=None)
        guess = self._snapshot(name="Guess", asset_count=1, birth_date=None, first_asset_date=None)

        clues = _compute_clues(target, guess, 0.42, 7)

        assert clues.ml_similarity == 0.42
        assert clues.assets_together == 7
