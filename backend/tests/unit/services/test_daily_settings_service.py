import pytest

from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_PERSON_ASSETS
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline import MODE_ARCADE as TIMELINE_MODE_ARCADE
from persistence.daily import DailyConfigModel
from services.daily_settings import InvalidGameSettingValueError, UnknownGameSettingError


@pytest.fixture(autouse=True)
def _clean_daily_configs(db_session):
    # Same rationale as test_game_settings_service.py's cleanup fixtures - daily_configs rows are
    # keyed by a fixed (game_type, mode), shared across every test in this file (no per-test DB
    # isolation, see conftest.py).
    def _clear():
        db_session.query(DailyConfigModel).filter(
            DailyConfigModel.game_type.in_([GEOGUESSR_TYPE, MORE_OR_LESS_TYPE])
        ).delete(synchronize_session=False)
        db_session.commit()

    _clear()
    yield
    _clear()


class TestGetSpecsAndSettings:
    def test_includes_the_normal_specs_plus_no_repeat_days(self, daily_settings_service):
        specs = daily_settings_service.get_specs(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)

        keys = {s.key for s in specs}
        assert "decay_km" in keys  # inherited from GAME_SETTING_SPECS
        assert "no_repeat_days" in keys

    def test_more_or_less_gets_chain_length_instead_of_no_repeat_days(self, daily_settings_service):
        specs = daily_settings_service.get_specs(MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS)

        keys = {s.key for s in specs}
        assert "chain_length" in keys
        assert "no_repeat_days" not in keys

    def test_timeline_gets_both_chain_length_and_no_repeat_days(self, daily_settings_service):
        # The first mode that needs both chain_length and no_repeat_days at once. The two tests
        # above already pin that Geoguessr/MoreOrLess keep their own single-spec behavior.
        specs = daily_settings_service.get_specs(TIMELINE_TYPE, TIMELINE_MODE_ARCADE)

        keys = {s.key for s in specs}
        assert "chain_length" in keys
        assert "no_repeat_days" in keys
        assert "tolerance_days" in keys  # inherited from GAME_SETTING_SPECS

    def test_no_row_means_disabled_with_defaults(self, daily_settings_service):
        enabled, values = daily_settings_service.get_config(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)

        assert enabled is False
        assert values["no_repeat_days"] == 30
        assert values["decay_km"] == 1500.0


class TestUpdateSettings:
    def test_can_enable_without_touching_values(self, daily_settings_service):
        enabled, values = daily_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, enabled=True
        )

        assert enabled is True
        assert values["decay_km"] == 1500.0  # untouched, still default

    def test_can_update_values_without_touching_enabled(self, daily_settings_service):
        daily_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, enabled=True)

        enabled, values = daily_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, values={"no_repeat_days": 10}
        )

        assert enabled is True  # unchanged by the values-only update
        assert values["no_repeat_days"] == 10

    def test_unknown_key_raises(self, daily_settings_service):
        with pytest.raises(UnknownGameSettingError):
            daily_settings_service.update_settings(
                GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, values={"not_a_real_key": 1}
            )

    def test_out_of_range_value_raises(self, daily_settings_service):
        with pytest.raises(InvalidGameSettingValueError):
            daily_settings_service.update_settings(
                GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, values={"no_repeat_days": 400}
            )


class TestResetSettings:
    def test_clears_value_overrides_but_keeps_enabled(self, daily_settings_service):
        daily_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, enabled=True, values={"no_repeat_days": 5}
        )

        enabled, values = daily_settings_service.reset_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)

        assert enabled is True  # "enabled no se resetea"
        assert values["no_repeat_days"] == 30
