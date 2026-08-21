"""Pure tests - no DB needed - for games/trivium/questions/_shared.py's distractor pickers, reused
across birthday_year/birthday_day_month/birthday_full_date/photos_first_asset_year."""

from datetime import date

from games.trivium.questions._shared import (
    pick_day_month_distractors,
    pick_distractor_years,
    pick_full_date_distractors,
)


class TestPickDistractorYears:
    def test_always_returns_three_distinct_years_other_than_correct(self):
        for _ in range(500):
            distractors = pick_distractor_years(correct_year=2000, min_year=1990, max_year=2010)
            assert len(distractors) == 3
            assert len(set(distractors)) == 3
            assert 2000 not in distractors
            assert all(1990 <= year <= 2010 for year in distractors)

    def test_works_at_the_minimum_generatable_span(self):
        # can_generate() only allows a caller through when max_year - min_year >= 3, i.e. exactly
        # 4 distinct integer years total - the tightest case that must still terminate.
        for _ in range(200):
            distractors = pick_distractor_years(correct_year=2000, min_year=2000, max_year=2003)
            assert sorted({*distractors, 2000}) == [2000, 2001, 2002, 2003]

    def test_works_when_correct_year_sits_at_the_edge_of_the_range(self):
        for _ in range(200):
            distractors = pick_distractor_years(correct_year=1990, min_year=1990, max_year=2010)
            assert len(set(distractors)) == 3
            assert 1990 not in distractors


class TestPickDayMonthDistractors:
    def test_always_returns_three_distinct_day_months_other_than_correct(self):
        correct = date(2001, 6, 15)
        for _ in range(300):
            distractors = pick_day_month_distractors(correct)
            keys = [(d.month, d.day) for d in distractors]
            assert len(keys) == 3
            assert len(set(keys)) == 3
            assert (correct.month, correct.day) not in keys

    def test_the_month_actually_varies_too_not_just_the_day(self):
        # Confirmed by the owner: this type has no year to vary, so both fields it does have
        # (day and month) should move - a too-narrow window would rarely, if ever, cross into a
        # different month.
        correct = date(2001, 6, 15)
        months_seen = set()
        for _ in range(200):
            for d in pick_day_month_distractors(correct):
                months_seen.add(d.month)
        assert months_seen != {correct.month}

    def test_wraps_correctly_across_a_year_boundary(self):
        # Real date arithmetic (not field-level day/month math) - Dec 30 + a few days must land in
        # January, not "day 33".
        correct = date(2001, 12, 30)
        for _ in range(100):
            for d in pick_day_month_distractors(correct):
                assert 1 <= d.month <= 12
                assert 1 <= d.day <= 31

    def test_never_introduces_29_february_unless_that_is_the_real_answer(self):
        correct = date(2001, 2, 20)
        for _ in range(300):
            for d in pick_day_month_distractors(correct):
                assert (d.month, d.day) != (2, 29)

    def test_29_february_can_still_be_the_correct_answer(self):
        # Not a distractor rule at all - the picker never even looks at `correct` for this check,
        # it only ever excludes 29 Feb from what it *generates*.
        correct = date(2000, 2, 29)
        distractors = pick_day_month_distractors(correct)
        assert (2, 29) not in [(d.month, d.day) for d in distractors]


class TestPickFullDateDistractors:
    def test_always_returns_three_distinct_dates_within_one_year_of_correct(self):
        correct = date(2001, 6, 15)
        for _ in range(300):
            distractors = pick_full_date_distractors(correct)
            assert len(distractors) == 3
            assert len(set(distractors)) == 3
            assert correct not in distractors
            assert all(correct.year - 1 <= d.year <= correct.year + 1 for d in distractors)

    def test_never_introduces_29_february_unless_that_is_the_real_answer(self):
        correct = date(2001, 2, 20)
        for _ in range(100):
            for d in pick_full_date_distractors(correct):
                assert (d.month, d.day) != (2, 29)

    def test_the_day_and_month_vary_as_widely_as_pick_day_month_distractors(self):
        correct = date(2001, 6, 15)
        months_seen = set()
        for _ in range(200):
            for d in pick_full_date_distractors(correct):
                months_seen.add(d.month)
        assert months_seen != {correct.month}

    def test_the_year_sometimes_differs_but_never_by_more_than_one(self):
        # Confirmed by the owner: this is the most specific of the three birthday_* types, so its
        # year noise is the tightest (+/-1) - unlike birthday_year's own wider spread.
        correct = date(2001, 6, 15)
        years_seen = set()
        for _ in range(200):
            for d in pick_full_date_distractors(correct):
                years_seen.add(d.year)
        assert years_seen != {correct.year}
        assert years_seen.issubset({correct.year - 1, correct.year, correct.year + 1})
