import pytest

from aivisibility.analysis.bootstrap import bootstrap_ci


def test_empty_input_returns_zeros():
    assert bootstrap_ci([]) == (0.0, 0.0, 0.0)


def test_point_estimate_is_sample_mean():
    point, _, _ = bootstrap_ci([True, False, True, True], seed=1)
    assert point == pytest.approx(0.75)


def test_seed_is_deterministic():
    data = [True] * 30 + [False] * 70
    assert bootstrap_ci(data, seed=42) == bootstrap_ci(data, seed=42)


def test_interval_brackets_point_estimate():
    data = [True] * 30 + [False] * 70
    point, lower, upper = bootstrap_ci(data, seed=0)
    assert lower <= point <= upper


def test_degenerate_sample_has_zero_width():
    _, lower, upper = bootstrap_ci([True] * 50, seed=0)
    assert lower == upper == 1.0


def test_interval_narrows_with_more_data():
    small = bootstrap_ci([True, False] * 10, seed=0)
    large = bootstrap_ci([True, False] * 200, seed=0)
    assert (large[2] - large[1]) < (small[2] - small[1])
