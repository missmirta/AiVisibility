"""Position bias: how often the model picks the option shown first."""

import numpy as np


def position_bias(picked_first: list[bool], n_boot: int = 1000, seed: int = 42, level: float = 0.95) -> dict:
    """`picked_first[i]` is True when answer i chose option A. 0.5 means no bias.
    Returns p_first and a bootstrap CI."""
    x = np.asarray(picked_first, dtype=float)
    if len(x) == 0:
        return {"p_first": float("nan"), "ci": (float("nan"), float("nan")), "n": 0}
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    alpha = (1 - level) / 2
    return {
        "p_first": float(x.mean()),
        "ci": (float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))),
        "n": len(x),
    }
