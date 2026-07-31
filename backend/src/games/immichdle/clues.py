"""Pure comparison logic for Immichdle's guess-relative-to-target clues (Age, AssetCount,
FirstAppearance, CommonNames, MLSimilarity, AssetsTogether - see games/immichdle/game.py's module
docstring). Split out from game.py so this logic - the exact "validación de pistas" the roadmap
calls out - is testable without constructing a whole game."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from games.immichdle.round import PersonSnapshot
from games.shared.serialization import DictCodec

AgeComparison = Literal["older", "younger", "same", "unknown"]
CountComparison = Literal["more", "less", "equal"]
DateComparison = Literal["before", "after", "same", "unknown"]


@dataclass(frozen=True)
class ImmichdleClues(DictCodec):
    age: AgeComparison
    asset_count: CountComparison
    first_appearance: DateComparison
    common_names: int
    ml_similarity: float | None
    assets_together: int
    # Magnitude buckets, not exact diffs - the target's birth_date/first_asset_date/asset_count stay
    # secret until the game ends, and an exact diff (e.g. "3 days younger") combined with the
    # guessed person's own public date/count would pin down the target's exact value from a single
    # guess, breaking the Wordle-style narrowing. None whenever the underlying comparison has no
    # meaningful magnitude ("same"/"equal"/"unknown").
    age_close: bool | None
    first_appearance_close: bool | None
    asset_count_close: bool | None
    # Only meaningful when age/first_appearance == "unknown" - that single enum value covers both
    # "neither person has a date" and "only the target's is missing" (the guess's own date, when
    # known, is already visible via ImmichdleRoundOut.guess_birth_date/guess_first_asset_date, so
    # only the "guess's date is also missing" case is actually ambiguous without this bit). Revealing
    # this one bit (not the target's date itself) is the same bucket-not-raw-value tradeoff as
    # *_close above.
    age_both_unknown: bool
    first_appearance_both_unknown: bool


def _is_close(target_date: date | None, guess_date: date | None) -> bool | None:
    """Whether two dates are within a year of each other - None if either is unknown."""
    if target_date is None or guess_date is None:
        return None
    return abs((guess_date - target_date).days) < 365


def _compute_clues(
    target: PersonSnapshot, guess: PersonSnapshot, ml_similarity: float | None, assets_together: int
) -> ImmichdleClues:
    """Every comparison is guess-relative-to-target (e.g. "older" means the guess is older than
    the target) - mirrors how more_or_less.py describes its candidate relative to its reference."""
    if target.birth_date is None or guess.birth_date is None:
        age: AgeComparison = "unknown"
    elif guess.birth_date < target.birth_date:
        age = "older"
    elif guess.birth_date > target.birth_date:
        age = "younger"
    else:
        age = "same"

    if guess.asset_count > target.asset_count:
        asset_count: CountComparison = "more"
    elif guess.asset_count < target.asset_count:
        asset_count = "less"
    else:
        asset_count = "equal"

    if target.first_asset_date is None or guess.first_asset_date is None:
        first_appearance: DateComparison = "unknown"
    elif guess.first_asset_date < target.first_asset_date:
        first_appearance = "before"
    elif guess.first_asset_date > target.first_asset_date:
        first_appearance = "after"
    else:
        first_appearance = "same"

    common_names = len(set(target.name.lower().split()) & set(guess.name.lower().split()))

    asset_count_close = None if asset_count == "equal" else abs(guess.asset_count - target.asset_count) < 100

    return ImmichdleClues(
        age=age,
        asset_count=asset_count,
        first_appearance=first_appearance,
        common_names=common_names,
        ml_similarity=ml_similarity,
        assets_together=assets_together,
        age_close=_is_close(target.birth_date, guess.birth_date) if age in ("older", "younger") else None,
        first_appearance_close=(
            _is_close(target.first_asset_date, guess.first_asset_date)
            if first_appearance in ("before", "after")
            else None
        ),
        asset_count_close=asset_count_close,
        age_both_unknown=target.birth_date is None and guess.birth_date is None,
        first_appearance_both_unknown=target.first_asset_date is None and guess.first_asset_date is None,
    )
