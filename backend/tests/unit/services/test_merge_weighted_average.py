"""merge_weighted_average is pure arithmetic (services/ml_service.py) - tested here against
synthetic vectors, no database, no MLService instance."""

import numpy as np
import pytest

from services.ml_service import merge_weighted_average


def test_simple_weighted_merge():
    result = merge_weighted_average([1.0, 2.0, 3.0], 2, [4.0, 5.0, 6.0], 1)

    assert result == pytest.approx([2.0, 3.0, 4.0])


def test_equal_counts_is_a_plain_average():
    result = merge_weighted_average([0.0, 0.0], 1, [2.0, 4.0], 1)

    assert result == pytest.approx([1.0, 2.0])


def test_zero_new_count_returns_the_old_average_unchanged():
    result = merge_weighted_average([1.0, 2.0], 5, [999.0, 999.0], 0)

    assert result == pytest.approx([1.0, 2.0])


def test_zero_old_count_returns_the_new_average_unchanged():
    result = merge_weighted_average([999.0, 999.0], 0, [3.0, 4.0], 7)

    assert result == pytest.approx([3.0, 4.0])


def test_matches_the_average_of_the_full_union_for_random_vectors():
    # The property merge_weighted_average is built on: the mean of a union of two disjoint sets
    # equals the count-weighted mean of the two sets' own means. Verified here against a random
    # partition rather than hand-picked numbers, so it isn't just confirming one lucky case.
    rng = np.random.default_rng(1234)
    all_vectors = rng.normal(size=(41, 12))
    split = 17
    old_vectors, new_vectors = all_vectors[:split], all_vectors[split:]

    merged = merge_weighted_average(
        old_vectors.mean(axis=0).tolist(),
        len(old_vectors),
        new_vectors.mean(axis=0).tolist(),
        len(new_vectors),
    )

    assert merged == pytest.approx(all_vectors.mean(axis=0).tolist())
