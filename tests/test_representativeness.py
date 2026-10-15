import numpy as np
import pytest

from aivisibility.analysis.bootstrap import bootstrap_ci
from aivisibility.representativeness.reweight import (
    compute_cluster_weights,
    effective_sample_size,
    weighted_bootstrap_ci,
)
from aivisibility.representativeness.two_sample import (
    classifier_two_sample_test,
    is_choice_question,
    length_matched_indices,
)


def _blob(rng, center, n, dim=8):
    return rng.normal(loc=center, scale=0.3, size=(n, dim))


def test_two_sample_same_distribution_is_near_chance():
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=(80, 8)), rng.normal(size=(120, 8))
    res = classifier_two_sample_test(a, b, seed=1, n_permutations=50)
    assert 0.35 < res.auc < 0.65
    assert res.p_value > 0.05


def test_two_sample_separated_distributions_is_detected():
    rng = np.random.default_rng(0)
    res = classifier_two_sample_test(_blob(rng, 0, 80), _blob(rng, 2, 120), seed=1, n_permutations=50)
    assert res.auc > 0.95
    assert res.p_value < 0.05
    assert (res.n_synthetic, res.n_real) == (80, 120)


def test_two_sample_is_reproducible_for_same_seed():
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=(60, 8)), rng.normal(loc=0.5, size=(90, 8))
    r1 = classifier_two_sample_test(a, b, seed=7, n_permutations=30)
    r2 = classifier_two_sample_test(a, b, seed=7, n_permutations=30)
    assert r1 == r2


def test_length_matched_picks_closest_unused_lengths():
    synthetic = ["a" * 10, "a" * 50]
    real = ["a" * 9, "a" * 12, "a" * 48, "a" * 200]
    assert length_matched_indices(synthetic, real) == [0, 2]


def test_is_choice_question():
    assert is_choice_question("Stripe vs Paddle for SaaS?")
    assert is_choice_question("Which payment gateway should I use?")
    assert not is_choice_question("How to encrypt card data in Java")


def test_cluster_weights_upweight_underrepresented_and_flag_uncovered():
    rng = np.random.default_rng(0)
    # synthetic: 30 in topic A, 10 in topic B; real: 10 in A, 30 in B, 20 in topic C (no synthetic)
    synthetic = np.vstack([_blob(rng, 0, 30), _blob(rng, 5, 10)])
    real = np.vstack([_blob(rng, 0, 10), _blob(rng, 5, 30), _blob(rng, -5, 20)])
    cw = compute_cluster_weights(synthetic, real, seed=0, k_range=range(3, 4))
    a, b = cw.synthetic_labels[0], cw.synthetic_labels[-1]
    assert cw.weights[a] == pytest.approx((10 / 60) / (30 / 40))  # shrunk
    assert cw.weights[b] == pytest.approx(min((30 / 60) / (10 / 40), 5.0))  # 2.0, grown
    assert len(cw.uncovered) == 1
    assert cw.weights[cw.uncovered[0]] == 0
    assert cw.p_real[cw.uncovered[0]] == pytest.approx(20 / 60)


def test_cluster_weights_are_clipped():
    rng = np.random.default_rng(0)
    synthetic = np.vstack([_blob(rng, 0, 39), _blob(rng, 5, 1)])
    real = np.vstack([_blob(rng, 0, 10), _blob(rng, 5, 30)])
    cw = compute_cluster_weights(synthetic, real, seed=0, k_range=range(2, 3), max_weight=5.0)
    assert cw.weights.max() == 5.0


def test_weighted_ci_with_equal_weights_matches_plain_bootstrap():
    values = [True] * 12 + [False] * 28
    plain = bootstrap_ci(values, n_resamples=500, seed=3)
    weighted = weighted_bootstrap_ci(values, [1.0] * 40, n_resamples=500, seed=3)
    assert weighted == pytest.approx(plain)


def test_weighted_point_follows_weights():
    values = [True, False]
    point, lower, upper = weighted_bootstrap_ci(values, [3.0, 1.0], n_resamples=200, seed=0)
    assert point == pytest.approx(0.75)
    assert lower <= point <= upper


def test_weighted_ci_empty_or_zero_weights():
    assert weighted_bootstrap_ci([], []) == (0.0, 0.0, 0.0)
    assert weighted_bootstrap_ci([True], [0.0]) == (0.0, 0.0, 0.0)


def test_effective_sample_size():
    assert effective_sample_size([1.0] * 10) == pytest.approx(10)
    assert effective_sample_size([4.0, 0.0, 0.0, 0.0]) == pytest.approx(1)
