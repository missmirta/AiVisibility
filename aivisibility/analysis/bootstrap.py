"""Own bootstrap confidence interval implementation.

Resamples with replacement at the response level (numpy, not
`scipy.stats.bootstrap`) so the method itself stays visible — same spirit
as the Bradley-Terry model planned for week 7.
"""

import numpy as np

from .precision import BOOTSTRAP_RESAMPLES


def bootstrap_ci(
    mentioned: list[bool],
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    ci: float = 0.95,
    seed: int | None = None,
) -> tuple[float, float, float]:
    """(point_estimate, lower, upper) mention-rate confidence interval.

    Draws `n_resamples` samples of the same length as `mentioned`, with
    replacement, takes the share of True in each, and returns the `ci`
    central percentile interval of that distribution (2.5/97.5 by default).
    """
    n = len(mentioned)
    if n == 0:
        return 0.0, 0.0, 0.0

    values = np.asarray(mentioned, dtype=np.float64)
    point = float(values.mean())

    rng = np.random.default_rng(seed)
    resample_idx = rng.integers(0, n, size=(n_resamples, n))
    resample_means = values[resample_idx].mean(axis=1)

    alpha = 1 - ci
    lower, upper = np.percentile(resample_means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return point, float(lower), float(upper)
