import pytest

from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_ALBUM_ASSETS, MODE_PERSON_ASSETS
from persistence.game_settings import GameSettingsModel
from services.game_settings import InvalidGameSettingValueError, UnknownGameSettingError


@pytest.fixture(autouse=True)
def _clean_geoguessr_settings(db_session):
    # Same rationale as test_admin_games_api.py's fixture of the same name - game_settings rows
    # are keyed by a fixed (game_type, mode), shared across every test (and test file) that
    # touches Geoguessr's settings, unlike the rest of this app's tests which isolate via unique
    # ids.
    def _clear():
        db_session.query(GameSettingsModel).filter(GameSettingsModel.game_type == GEOGUESSR_TYPE).delete()
        db_session.commit()

    _clear()
    yield
    _clear()


@pytest.fixture(autouse=True)
def _clean_more_or_less_settings(db_session):
    # Needed by TestSettingsAreIndependentPerMode below, which inserts raw rows for both of
    # MoreOrLess's modes directly.
    def _clear():
        db_session.query(GameSettingsModel).filter(GameSettingsModel.game_type == MORE_OR_LESS_TYPE).delete()
        db_session.commit()

    _clear()
    yield
    _clear()


class TestGetSettings:
    def test_no_override_returns_defaults(self, game_settings_service):
        settings = game_settings_service.get_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)

        assert settings["decay_km"] == 1500.0
        assert settings["total_rounds"] == 5

    def test_game_type_with_no_specs_returns_empty_dict(self, game_settings_service):
        assert game_settings_service.get_settings(MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS) == {}

    def test_unknown_game_type_returns_empty_dict(self, game_settings_service):
        assert game_settings_service.get_settings("not-a-real-game", MODE_DISTANCE_BETWEEN_GUESS) == {}

    def test_unknown_mode_for_a_known_game_type_returns_empty_dict(self, game_settings_service):
        assert game_settings_service.get_settings(GEOGUESSR_TYPE, "not-a-real-mode") == {}


class TestUpdateSettings:
    def test_overrides_only_the_given_keys(self, game_settings_service):
        updated = game_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"decay_km": 900.0}
        )

        assert updated["decay_km"] == 900.0
        assert updated["total_rounds"] == 5  # untouched key still falls back to its default

    def test_persists_across_a_fresh_read(self, game_settings_service):
        game_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"total_rounds": 8})

        assert game_settings_service.get_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)["total_rounds"] == 8

    def test_a_second_update_merges_with_the_first(self, game_settings_service):
        game_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"decay_km": 900.0})
        updated = game_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"total_rounds": 8}
        )

        assert updated["decay_km"] == 900.0
        assert updated["total_rounds"] == 8

    def test_unknown_key_raises(self, game_settings_service):
        with pytest.raises(UnknownGameSettingError):
            game_settings_service.update_settings(
                GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"not_a_real_key": 1}
            )

    def test_value_below_min_raises(self, game_settings_service):
        with pytest.raises(InvalidGameSettingValueError):
            game_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"total_rounds": 0})

    def test_value_above_max_raises(self, game_settings_service):
        with pytest.raises(InvalidGameSettingValueError):
            game_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"total_rounds": 51})

    def test_nan_raises(self, game_settings_service):
        with pytest.raises(InvalidGameSettingValueError):
            game_settings_service.update_settings(
                GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"decay_km": float("nan")}
            )

    def test_positive_infinity_raises(self, game_settings_service):
        with pytest.raises(InvalidGameSettingValueError):
            game_settings_service.update_settings(
                GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"decay_km": float("inf")}
            )

    def test_negative_infinity_raises(self, game_settings_service):
        with pytest.raises(InvalidGameSettingValueError):
            game_settings_service.update_settings(
                GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"decay_km": float("-inf")}
            )

    def test_nan_for_an_int_spec_raises_the_typed_error(self, game_settings_service):
        # Without the isfinite guard running first, int(float("nan")) raises a raw ValueError here
        # instead of the typed InvalidGameSettingValueError main.py knows how to map to a 400.
        with pytest.raises(InvalidGameSettingValueError):
            game_settings_service.update_settings(
                GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"total_rounds": float("nan")}
            )

    def test_non_integer_value_for_an_int_spec_raises(self, game_settings_service):
        with pytest.raises(InvalidGameSettingValueError):
            game_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"total_rounds": 5.5})

    def test_float_spec_accepts_a_decimal_value(self, game_settings_service):
        updated = game_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"decay_km": 900.5}
        )

        assert updated["decay_km"] == 900.5


class TestResetSettings:
    def test_clears_a_previous_override(self, game_settings_service):
        game_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, {"decay_km": 900.0})

        reset = game_settings_service.reset_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)

        assert reset["decay_km"] == 1500.0
        assert game_settings_service.get_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)["decay_km"] == 1500.0

    def test_is_a_no_op_when_there_was_no_override(self, game_settings_service):
        assert game_settings_service.reset_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)["decay_km"] == 1500.0


class TestSettingsAreIndependentPerMode:
    """Roadmap #f - proves the composite (game_type, mode) primary key actually isolates two modes
    of the same game_type, using MoreOrLess (the one real game with two modes today) even though
    neither mode has a registered SettingSpec (see services/game_settings.py's module docstring) -
    inserts raw rows directly via db_session, bypassing update_settings's spec validation, purely
    to exercise the read path (GameSettingsService.get_settings) against the composite key. No
    real game currently has two modes that both accept configurable settings, so this is the
    closest same-repo proof available that the migration's composite key isolates rows correctly."""

    def test_two_modes_of_the_same_game_type_do_not_collide(self, db_session, game_settings_service):
        db_session.add(GameSettingsModel(game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, values={"probe": 1.0}))
        db_session.add(GameSettingsModel(game_type=MORE_OR_LESS_TYPE, mode=MODE_ALBUM_ASSETS, values={"probe": 2.0}))
        db_session.commit()

        assert game_settings_service.get_settings(MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS) == {"probe": 1.0}
        assert game_settings_service.get_settings(MORE_OR_LESS_TYPE, MODE_ALBUM_ASSETS) == {"probe": 2.0}
