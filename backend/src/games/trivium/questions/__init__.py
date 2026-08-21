"""Trivium's question-type bank - see questions/base.py for the QuestionType contract every module
here implements, and games/trivium/modes.py for which types each mode enables. Re-exports the
public surface so `from games.trivium.questions import BirthYearQuestion` (the mode registry,
tests) keeps working unchanged."""

from games.trivium.questions.base import GeneratedQuestion, MediaKind, MediaSpec, QuestionType
from games.trivium.questions.birthday_day_month import BirthdayDayMonthQuestion
from games.trivium.questions.birthday_full_date import BirthdayFullDateQuestion
from games.trivium.questions.birthday_year import BirthYearQuestion
from games.trivium.questions.location_city import LocationCityQuestion
from games.trivium.questions.location_country import LocationCountryQuestion
from games.trivium.questions.photos_first_asset_year import PhotosFirstAssetYearQuestion
from games.trivium.questions.photos_together import PhotosTogetherQuestion
from games.trivium.questions.photos_total_assets import PhotosTotalAssetsQuestion

__all__ = [
    "BirthYearQuestion",
    "BirthdayDayMonthQuestion",
    "BirthdayFullDateQuestion",
    "GeneratedQuestion",
    "LocationCityQuestion",
    "LocationCountryQuestion",
    "MediaKind",
    "MediaSpec",
    "PhotosFirstAssetYearQuestion",
    "PhotosTogetherQuestion",
    "PhotosTotalAssetsQuestion",
    "QuestionType",
]
