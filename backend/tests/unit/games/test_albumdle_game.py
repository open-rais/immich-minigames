from datetime import date
from uuid import UUID, uuid4

import pytest

from games.immichdle import (
    AlbumdleGame,
    AlbumSnapshot,
    DuplicateGuessError,
    InvalidGuessError,
    _compute_album_clues,
)
from games.immichdle.albumdle import ASSET_COUNT_WEIGHT_EXPONENT


def _wrong_album_id(immich_service, game: AlbumdleGame) -> UUID:
    [candidate] = immich_service.get_albums(
        limit=1, min_asset_count=1, exclude_ids=frozenset({game.target.id})
    )
    return candidate.id


class TestAlbumdleGame:
    def test_starts_with_score_100_and_one_pending_round(self, immich_service):
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service)

        assert game.score == 100
        assert game.finished is False
        assert len(game.rounds) == 1
        assert game.current_round.answered is False

    def test_correct_guess_wins_without_losing_points(self, immich_service):
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service)

        result = game.play_round(game.target.id)

        assert result.score_delta == 0
        assert result.score == 100
        assert result.finished is True
        assert game.rounds[-1].correct is True

    def test_wrong_guess_subtracts_five_and_continues(self, immich_service):
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service)
        wrong_id = _wrong_album_id(immich_service, game)

        result = game.play_round(wrong_id)

        assert result.score_delta == -5
        assert result.score == 95
        assert result.finished is False
        assert len(game.rounds) == 2
        assert game.rounds[0].correct is False
        assert game.rounds[0].guessed_album is not None
        assert game.rounds[0].clues is not None

    def test_score_floors_at_zero_and_ends_the_game(self, immich_service):
        # A small starting_score (rather than assuming the dev library has ~20 albums besides the
        # target, like persondle's equivalent test does for named people) keeps this independent
        # of how many albums happen to exist right now.
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service, settings={"starting_score": 10})
        wrong_candidates = immich_service.get_albums(
            limit=5, min_asset_count=1, exclude_ids=frozenset({game.target.id})
        )
        assert len(wrong_candidates) >= 2, "dev data needs at least 2 albums besides the target"

        for candidate in wrong_candidates:
            if game.finished:
                break
            game.play_round(candidate.id)

        assert game.finished is True
        assert game.score == 0

    def test_duplicate_guess_raises(self, immich_service):
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service)
        wrong_id = _wrong_album_id(immich_service, game)
        game.play_round(wrong_id)

        with pytest.raises(DuplicateGuessError):
            game.play_round(wrong_id)

    def test_invalid_album_id_raises(self, immich_service):
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service)

        with pytest.raises(InvalidGuessError):
            game.play_round(uuid4())

    def test_playing_an_already_finished_game_raises(self, immich_service):
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service)
        game.play_round(game.target.id)

        with pytest.raises(ValueError):
            game.play_round(game.target.id)

    def test_starting_with_no_albums_raises_a_friendly_error(self, immich_service, monkeypatch):
        monkeypatch.setattr(immich_service, "get_albums", lambda **kwargs: [])

        with pytest.raises(ValueError, match="not enough albums"):
            AlbumdleGame.start(id=uuid4(), immich_service=immich_service)


class TestAlbumdleAdminSettings:
    """Confirms an override actually changes live behavior, not just what
    GameSettingsService reports (see test_game_settings_service.py for that)."""

    def test_starting_score_override_changes_the_initial_score(self, immich_service):
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service, settings={"starting_score": 50})

        assert game.score == 50

    def test_wrong_guess_penalty_override_changes_the_score_delta(self, immich_service):
        game = AlbumdleGame.start(id=uuid4(), immich_service=immich_service, settings={"wrong_guess_penalty": 20})
        wrong_id = _wrong_album_id(immich_service, game)

        result = game.play_round(wrong_id)

        assert result.score_delta == -20

    def _spy_on_target_selection_call(self, immich_service, monkeypatch) -> list[dict]:
        """Records the kwargs of start()'s single get_albums() call (target selection) - mirrors
        test_persondle_game.py's identical spy."""
        calls: list[dict] = []
        real_get_albums = immich_service.get_albums

        def _spy(**kwargs):
            calls.append(kwargs)
            return real_get_albums(**kwargs)

        monkeypatch.setattr(immich_service, "get_albums", _spy)
        return calls

    def test_asset_count_weight_override_is_forwarded_to_target_selection(self, immich_service, monkeypatch):
        calls = self._spy_on_target_selection_call(immich_service, monkeypatch)

        AlbumdleGame.start(id=uuid4(), immich_service=immich_service, settings={"asset_count_weight": 0.7})

        assert calls[0]["asset_count_weight"] == 0.7

    def test_asset_count_weight_defaults_when_not_overridden(self, immich_service, monkeypatch):
        calls = self._spy_on_target_selection_call(immich_service, monkeypatch)

        AlbumdleGame.start(id=uuid4(), immich_service=immich_service)

        assert calls[0]["asset_count_weight"] == ASSET_COUNT_WEIGHT_EXPONENT


class TestComputeAlbumClues:
    """Isolated from the DB - constructs snapshots directly to deterministically exercise every
    clue direction, same style as test_persondle_game.py's TestComputePersonClues."""

    def _snapshot(
        self,
        *,
        name: str,
        asset_count: int,
        first_asset_date: date | None,
        dominant_person_ids: tuple[UUID, ...] = (),
        dominant_person_name: str | None = None,
        unique_named_person_count: int = 0,
    ) -> AlbumSnapshot:
        return AlbumSnapshot(
            id=uuid4(),
            name=name,
            asset_count=asset_count,
            first_asset_date=first_asset_date,
            dominant_person_ids=dominant_person_ids,
            dominant_person_name=dominant_person_name,
            unique_named_person_count=unique_named_person_count,
        )

    def test_first_asset_date_before_after_same_unknown(self):
        target = self._snapshot(name="Target", asset_count=1, first_asset_date=date(2015, 6, 1))
        before = self._snapshot(name="Before", asset_count=1, first_asset_date=date(2010, 1, 1))
        after = self._snapshot(name="After", asset_count=1, first_asset_date=date(2020, 1, 1))
        same = self._snapshot(name="Same", asset_count=1, first_asset_date=date(2015, 6, 1))
        unknown = self._snapshot(name="Unknown", asset_count=1, first_asset_date=None)

        assert _compute_album_clues(target, before, None, None).first_asset_date == "before"
        assert _compute_album_clues(target, after, None, None).first_asset_date == "after"
        assert _compute_album_clues(target, same, None, None).first_asset_date == "same"
        assert _compute_album_clues(target, unknown, None, None).first_asset_date == "unknown"

    def test_first_asset_date_close_bucket(self):
        target = self._snapshot(name="Target", asset_count=1, first_asset_date=date(2015, 6, 1))
        close = self._snapshot(name="Close", asset_count=1, first_asset_date=date(2015, 1, 1))
        far = self._snapshot(name="Far", asset_count=1, first_asset_date=date(2010, 1, 1))

        assert _compute_album_clues(target, close, None, None).first_asset_date_close is True
        assert _compute_album_clues(target, far, None, None).first_asset_date_close is False

    def test_first_asset_date_both_unknown_distinguishes_from_one_unknown(self):
        known_target = self._snapshot(name="Target", asset_count=1, first_asset_date=date(2015, 6, 1))
        unknown_target = self._snapshot(name="Target", asset_count=1, first_asset_date=None)
        known_guess = self._snapshot(name="Guess", asset_count=1, first_asset_date=date(2015, 6, 1))
        unknown_guess = self._snapshot(name="Guess", asset_count=1, first_asset_date=None)

        assert _compute_album_clues(unknown_target, unknown_guess, None, None).first_asset_date_both_unknown is True
        assert _compute_album_clues(known_target, unknown_guess, None, None).first_asset_date_both_unknown is False
        assert _compute_album_clues(unknown_target, known_guess, None, None).first_asset_date_both_unknown is False

    def test_asset_count_more_less_equal(self):
        target = self._snapshot(name="Target", asset_count=10, first_asset_date=None)
        more = self._snapshot(name="More", asset_count=20, first_asset_date=None)
        less = self._snapshot(name="Less", asset_count=5, first_asset_date=None)
        equal = self._snapshot(name="Equal", asset_count=10, first_asset_date=None)

        assert _compute_album_clues(target, more, None, None).asset_count == "more"
        assert _compute_album_clues(target, less, None, None).asset_count == "less"
        assert _compute_album_clues(target, equal, None, None).asset_count == "equal"

    def test_unique_face_count_more_less_equal(self):
        target = self._snapshot(name="Target", asset_count=1, first_asset_date=None, unique_named_person_count=5)
        more = self._snapshot(name="More", asset_count=1, first_asset_date=None, unique_named_person_count=10)
        less = self._snapshot(name="Less", asset_count=1, first_asset_date=None, unique_named_person_count=2)

        assert _compute_album_clues(target, more, None, None).unique_face_count == "more"
        assert _compute_album_clues(target, less, None, None).unique_face_count == "less"

    def test_common_names_counts_shared_tokens_case_insensitively(self):
        target = self._snapshot(name="Colbun 2022", asset_count=1, first_asset_date=None)
        guess = self._snapshot(name="colbun 2023", asset_count=1, first_asset_date=None)
        stranger = self._snapshot(name="Tailandia", asset_count=1, first_asset_date=None)

        assert _compute_album_clues(target, guess, None, None).common_names == 1
        assert _compute_album_clues(target, stranger, None, None).common_names == 0

    def test_similarity_passes_through_unchanged(self):
        target = self._snapshot(name="Target", asset_count=1, first_asset_date=None)
        guess = self._snapshot(name="Guess", asset_count=1, first_asset_date=None)

        assert _compute_album_clues(target, guess, 0.42, None).similarity == 0.42

    def test_dominant_face_reflects_the_guess_not_the_target(self):
        person_id = uuid4()
        target = self._snapshot(name="Target", asset_count=1, first_asset_date=None)
        guess = self._snapshot(
            name="Guess",
            asset_count=1,
            first_asset_date=None,
            dominant_person_ids=(person_id,),
            dominant_person_name="Someone",
        )

        clues = _compute_album_clues(target, guess, None, "match")

        assert clues.dominant_face_person_id == person_id
        assert clues.dominant_face_name == "Someone"
        assert clues.dominant_face_extra_count == 0
        assert clues.dominant_face_comparison == "match"

    def test_dominant_face_extra_count_reflects_tie_size(self):
        target = self._snapshot(name="Target", asset_count=1, first_asset_date=None)
        guess = self._snapshot(
            name="Guess",
            asset_count=1,
            first_asset_date=None,
            dominant_person_ids=(uuid4(), uuid4(), uuid4()),
            dominant_person_name="Someone",
        )

        clues = _compute_album_clues(target, guess, None, "miss")

        assert clues.dominant_face_extra_count == 2

    def test_dominant_face_comparison_none_when_guess_has_no_named_face(self):
        target = self._snapshot(name="Target", asset_count=1, first_asset_date=None)
        guess = self._snapshot(name="Guess", asset_count=1, first_asset_date=None)

        clues = _compute_album_clues(target, guess, None, None)

        assert clues.dominant_face_person_id is None
        assert clues.dominant_face_comparison is None
