import numpy as np

from aivisibility.analysis.convergence import subsample_curve


def _pool(n=60, rate=0.3, seed=1):
    rng = np.random.default_rng(seed)
    return (rng.random(n) < rate).tolist()


def test_curve_is_deterministic_with_seed():
    pool = _pool()
    a = subsample_curve(pool, sizes=[5, 20, 60], seed=7)
    b = subsample_curve(pool, sizes=[5, 20, 60], seed=7)
    assert a == b


def test_curve_stable_across_seeds_within_tolerance():
    # Different seeds must agree to within a few tolerances: the stopping rule
    # bounds the curve's own Monte Carlo noise, not just the average draw count.
    pool = _pool()
    widths = [
        subsample_curve(pool, sizes=[20], seed=s, tol_pp=0.5)[0].avg_half_width_pp
        for s in range(5)
    ]
    assert max(widths) - min(widths) < 4 * 0.5


def test_full_pool_not_resampled_and_width_shrinks():
    pool = _pool()
    curve = subsample_curve(pool, sizes=[5, 30, 60], seed=3)
    assert [p.n for p in curve] == [5, 30, 60]
    assert curve[0].avg_half_width_pp > curve[1].avg_half_width_pp > curve[2].avg_half_width_pp
