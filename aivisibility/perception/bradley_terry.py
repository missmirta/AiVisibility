"""Bradley-Terry strengths from pairwise wins, with bootstrap intervals.

P(i beats j) = sigmoid(theta_i - theta_j). A small L2 penalty keeps theta
finite when a brand never loses; theta is centered to sum to 0.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.special import expit


def wins_matrix(brands: list[str], winners: list[str], losers: list[str]) -> np.ndarray:
    idx = {b: i for i, b in enumerate(brands)}
    wins = np.zeros((len(brands), len(brands)))
    for win, lose in zip(winners, losers):
        wins[idx[win], idx[lose]] += 1
    return wins


def fit_bradley_terry(wins: np.ndarray, reg: float = 0.1) -> np.ndarray:
    """MAP estimate of theta from a wins matrix (wins[i, j] = times i beat j)."""
    n = wins.shape[0]

    def neg_log_posterior(theta: np.ndarray) -> tuple[float, np.ndarray]:
        diff = theta[:, None] - theta[None, :]
        p = expit(diff)
        loglik = np.sum(wins * -np.logaddexp(0, -diff))
        grad = (wins * (1 - p)).sum(axis=1) - (wins.T * (1 - p)).sum(axis=1)
        value = -loglik + 0.5 * reg * theta @ theta
        return value, -grad + reg * theta

    res = minimize(neg_log_posterior, np.zeros(n), jac=True, method="L-BFGS-B")
    return res.x - res.x.mean()


def is_separated(wins: np.ndarray) -> bool:
    """True when the win graph (i -> j if i beat j at least once) is not strongly connected.
    Then the unpenalized MLE does not exist, and theta is set by the L2 penalty rather than
    the data: read only the ranking, not the size of theta."""
    n_components, _ = connected_components(csr_matrix(wins > 0), directed=True, connection="strong")
    return n_components > 1


@dataclass
class BTResult:
    brands: list[str]
    theta: np.ndarray
    ci_low: np.ndarray
    ci_high: np.ndarray
    separated: bool = False


def bootstrap_bt(
    brands: list[str],
    winners: list[str],
    losers: list[str],
    n_boot: int = 1000,
    seed: int = 42,
    level: float = 0.95,
    reg: float = 0.1,
    groups: list | None = None,
) -> BTResult:
    """Fit on all outcomes, then resample for the CI.

    With `groups` (one hashable label per outcome) whole groups are resampled together, so
    correlated repeats of the same cell count once (cluster bootstrap). Without it every
    outcome is resampled on its own."""
    n_brands = len(brands)
    wins_all = wins_matrix(brands, winners, losers)
    theta = fit_bradley_terry(wins_all, reg)
    idx = {b: i for i, b in enumerate(brands)}
    labels = list(range(len(winners))) if groups is None else groups
    keys = {k: i for i, k in enumerate(dict.fromkeys(labels))}
    per_group = np.zeros((len(keys), n_brands, n_brands))
    for w, lo, g in zip(winners, losers, labels):
        per_group[keys[g], idx[w], idx[lo]] += 1
    rng = np.random.default_rng(seed)
    draws = np.empty((n_boot, n_brands))
    for k in range(n_boot):
        pick = rng.integers(0, len(keys), len(keys))
        draws[k] = fit_bradley_terry(per_group[pick].sum(axis=0), reg)
    alpha = (1 - level) / 2
    return BTResult(
        brands=list(brands),
        theta=theta,
        ci_low=np.quantile(draws, alpha, axis=0),
        ci_high=np.quantile(draws, 1 - alpha, axis=0),
        separated=is_separated(wins_all),
    )
