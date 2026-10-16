"""Turn stored pairwise answers into the perception map (no API calls).

Input rows are dict-like with: engine, attribute, context, brand_first, brand_second, winner
(None for an unparsed or failed answer).
"""

from collections import defaultdict
from itertools import combinations

import numpy as np
from scipy.stats import spearmanr

from .bradley_terry import BTResult, bootstrap_bt
from .position_bias import position_bias


def perception_map(
    rows, brands: list[str], n_boot: int = 1000, seed: int = 42
) -> dict[tuple[str, str], BTResult]:
    """(engine, attribute) -> Bradley-Terry strengths with cluster-bootstrap CI (by pair and context)."""
    groups = defaultdict(lambda: ([], [], []))
    for r in rows:
        if r["winner"] is None:
            continue
        loser = r["brand_second"] if r["winner"] == r["brand_first"] else r["brand_first"]
        winners, losers, cells = groups[(r["engine"], r["attribute"])]
        winners.append(r["winner"])
        losers.append(loser)
        # Repeats and both orders of one (pair, context) cell are correlated: resample them together.
        cells.append((frozenset((r["brand_first"], r["brand_second"])), r["context"]))
    return {
        key: bootstrap_bt(brands, w, lo, n_boot=n_boot, seed=seed, groups=cells)
        for key, (w, lo, cells) in sorted(groups.items())
    }


def overlapping_pairs(result: BTResult) -> list[tuple[str, str]]:
    """Brand pairs whose CIs overlap, i.e. pairs we cannot rank."""
    out = []
    for i, j in combinations(range(len(result.brands)), 2):
        if result.ci_low[i] <= result.ci_high[j] and result.ci_low[j] <= result.ci_high[i]:
            out.append((result.brands[i], result.brands[j]))
    return out


def engine_stats(rows, n_boot: int = 1000, seed: int = 42) -> dict[str, dict]:
    """Per engine: answers, invalid share and position bias (share of "A" picks)."""
    by_engine = defaultdict(list)
    for r in rows:
        by_engine[r["engine"]].append(r)
    stats = {}
    for engine, rs in sorted(by_engine.items()):
        valid = [r for r in rs if r["winner"] is not None]
        picked_first = [r["winner"] == r["brand_first"] for r in valid]
        stats[engine] = {
            "n": len(rs),
            "invalid_share": 1 - len(valid) / len(rs),
            "position": position_bias(picked_first, n_boot=n_boot, seed=seed),
        }
    return stats


def count_cycles(rows, brands: list[str]) -> dict[tuple[str, str], int]:
    """(engine, attribute) -> number of intransitive triples (A>B, B>C, C>A by majority).
    Pairs with equal wins have no majority and are skipped."""
    wins = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["winner"] is None:
            continue
        loser = r["brand_second"] if r["winner"] == r["brand_first"] else r["brand_first"]
        wins[(r["engine"], r["attribute"])][(r["winner"], loser)] += 1
    out = {}
    for key, w in sorted(wins.items()):
        beats = {(a, b) for a in brands for b in brands if a != b and w[(a, b)] > w[(b, a)]}
        out[key] = sum(
            ((a, b) in beats and (b, c) in beats and (c, a) in beats)
            or ((b, a) in beats and (c, b) in beats and (a, c) in beats)
            for a, b, c in combinations(brands, 3)
        )
    return out


def engine_agreement(result_map: dict[tuple[str, str], BTResult], engines: tuple[str, str]) -> dict:
    """Per attribute, Spearman correlation of the two engines' theta vectors."""
    out = {}
    attributes = {attr for _, attr in result_map}
    for attr in sorted(attributes):
        a, b = result_map.get((engines[0], attr)), result_map.get((engines[1], attr))
        if a is None or b is None:
            continue
        out[attr] = float(spearmanr(a.theta, b.theta).statistic) if np.ptp(a.theta) and np.ptp(b.theta) else float("nan")
    return out
