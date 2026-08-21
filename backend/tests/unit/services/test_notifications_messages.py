from uuid import uuid4

import pytest

from services.notifications.content import AlbumAnniversaryEntry, BirthdayEntry
from services.notifications.messages import (
    album_anniversary,
    birthdays,
    daily_available,
    daily_reminder_generic,
    daily_reminder_streak_at_risk,
    game_display_name,
)

_LANGUAGES = ["en", "es", "fr", "de"]


class TestRendersWithoutErrorsInEveryLanguage:
    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_daily_available(self, language):
        message = daily_available(language)
        assert message.title
        assert message.body

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_daily_reminder_streak_at_risk_interpolates_streak_and_game(self, language):
        message = daily_reminder_streak_at_risk(language, "geoguessr", 5)
        assert "5" in message.body
        assert game_display_name("geoguessr", language) in message.body

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_daily_reminder_generic(self, language):
        message = daily_reminder_generic(language)
        assert message.body

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_birthdays_singular_interpolates_name_and_age(self, language):
        entries = [BirthdayEntry(person_id=uuid4(), name="María", age=34)]
        message = birthdays(language, entries)
        assert "María" in message.body
        assert "34" in message.body

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_birthdays_plural_interpolates_every_name(self, language):
        entries = [
            BirthdayEntry(person_id=uuid4(), name="María", age=34),
            BirthdayEntry(person_id=uuid4(), name="Juan", age=8),
        ]
        message = birthdays(language, entries)
        assert "María" in message.body
        assert "Juan" in message.body

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_album_anniversary_singular_interpolates_name_and_years(self, language):
        entries = [AlbumAnniversaryEntry(album_id=uuid4(), name="Verano 2020", years_ago=6)]
        message = album_anniversary(language, entries)
        assert "Verano 2020" in message.body
        assert "6" in message.body

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_album_anniversary_plural_interpolates_the_count(self, language):
        entries = [
            AlbumAnniversaryEntry(album_id=uuid4(), name="Verano 2020", years_ago=6),
            AlbumAnniversaryEntry(album_id=uuid4(), name="Invierno 2019", years_ago=7),
        ]
        message = album_anniversary(language, entries)
        assert "2" in message.body


class TestFallback:
    def test_an_unknown_language_falls_back_to_english(self):
        message = daily_available("xx")
        assert message.title == daily_available("en").title

    def test_an_unknown_game_type_falls_back_to_its_own_identifier(self):
        assert game_display_name("some-future-game", "es") == "some-future-game"
