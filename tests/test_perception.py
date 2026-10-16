import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from aivisibility.common import db
from aivisibility.perception.bradley_terry import bootstrap_bt, fit_bradley_terry, is_separated, wins_matrix
from aivisibility.perception.pairs import build_comparisons
from aivisibility.perception.parse import parse_choice
from aivisibility.perception.position_bias import position_bias
from aivisibility.prober.base import ProbeResult

BRANDS = ["Stripe", "Paddle", "Adyen", "PayPal"]


def test_build_comparisons_covers_both_orders():
    cs = build_comparisons(BRANDS)
    assert len(cs) == 6 * 7 * 2 * 5 * 2
    cell = [
        c for c in cs
        if c.attribute == "cheap" and c.context == "a small SaaS startup"
        and c.repeat == 0 and {c.first, c.second} == {"Stripe", "Paddle"}
    ]
    assert {(c.first, c.second) for c in cell} == {("Stripe", "Paddle"), ("Paddle", "Stripe")}


def test_winner_maps_letter_to_brand():
    c = build_comparisons(["X", "Y"], {"cheap": "cheaper"}, ["ctx"], 1)[0]
    assert c.winner("A") == c.first and c.winner("B") == c.second and c.winner(None) is None


@pytest.mark.parametrize("text,expected", [
    ("A", "A"), ("B.", "B"), (" b ", "B"), ("Answer: B", "B"), ("Option A", "A"),
    ("A) Stripe", "A"), ("A or B", None), ("A/B", None), ("", None), (None, None),
    ("I cannot compare these providers.", None), ("A great question, but it depends on ...", None),
])
def test_parse_choice(text, expected):
    assert parse_choice(text) == expected


def _simulate(theta, n, seed):
    rng = np.random.default_rng(seed)
    winners, losers = [], []
    for _ in range(n):
        i, j = rng.choice(len(BRANDS), 2, replace=False)
        p = 1 / (1 + np.exp(-(theta[i] - theta[j])))
        w, lo = (i, j) if rng.random() < p else (j, i)
        winners.append(BRANDS[w])
        losers.append(BRANDS[lo])
    return winners, losers


def test_bt_recovers_known_ranking():
    theta = np.array([1.0, 0.3, -0.3, -1.0])
    w, lo = _simulate(theta, 2000, seed=1)
    est = fit_bradley_terry(wins_matrix(BRANDS, w, lo))
    assert list(np.argsort(-est)) == [0, 1, 2, 3]
    assert np.allclose(est, theta, atol=0.25)
    assert abs(est.sum()) < 1e-6


def test_bt_finite_when_brand_never_loses():
    wins = np.array([[0, 10, 10], [0, 0, 5], [0, 0, 0]], dtype=float)
    est = fit_bradley_terry(wins)
    assert np.all(np.isfinite(est)) and est[0] > est[1] > est[2]


def test_bt_equal_brands_near_zero():
    w, lo = _simulate(np.zeros(4), 2000, seed=2)
    assert np.allclose(fit_bradley_terry(wins_matrix(BRANDS, w, lo)), 0, atol=0.15)


def test_bootstrap_is_seeded_and_ci_covers_estimate():
    w, lo = _simulate(np.array([0.8, 0.2, -0.2, -0.8]), 400, seed=3)
    a = bootstrap_bt(BRANDS, w, lo, n_boot=200, seed=7)
    b = bootstrap_bt(BRANDS, w, lo, n_boot=200, seed=7)
    assert np.array_equal(a.ci_low, b.ci_low) and np.array_equal(a.ci_high, b.ci_high)
    assert np.all(a.ci_low <= a.theta + 1e-9) and np.all(a.theta <= a.ci_high + 1e-9)


def test_position_bias_detects_always_a():
    biased = position_bias([True] * 90 + [False] * 10, n_boot=200)
    fair = position_bias([True, False] * 50, n_boot=200)
    assert biased["p_first"] == 0.9 and biased["ci"][0] > 0.8
    assert fair["p_first"] == 0.5 and fair["ci"][0] < 0.5 < fair["ci"][1]
    assert position_bias([])["n"] == 0


def _load_run_pairwise():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_pairwise.py"
    spec = importlib.util.spec_from_file_location("run_pairwise", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_pairwise"] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeProber:
    def __init__(self, text="A", cost=0.01):
        self.text, self.cost, self.calls = text, cost, 0

    async def probe(self, prompt):
        self.calls += 1
        return ProbeResult(self.text, 10, 1, self.cost, 5, "fake")


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")


async def test_run_pairwise_dry_run_makes_no_calls(tmp_db, capsys):
    run = _load_run_pairwise()
    fake = FakeProber()
    await run.main(True, None, None, None, probers={"openai": fake})
    assert fake.calls == 0 and "840 requests" in capsys.readouterr().out


async def test_run_pairwise_stores_rows_and_respects_budget(tmp_db):
    run = _load_run_pairwise()
    fake = FakeProber(cost=0.01)
    await run.main(False, 0.05, None, 100, probers={"openai": fake})
    rows = db.get_pairwise_responses()
    assert len(rows) == fake.calls == 5
    assert all(r["choice"] == "A" and r["winner"] == r["brand_first"] for r in rows)


def test_is_separated_detects_unconnected_win_graph():
    chain = np.array([[0, 5, 5], [0, 0, 5], [0, 0, 0]], dtype=float)  # 0 > 1 > 2, nobody loses upwards
    cycle = np.array([[0, 5, 1], [1, 0, 5], [5, 1, 0]], dtype=float)  # everyone beats someone
    assert is_separated(chain) and not is_separated(cycle)


def test_cluster_bootstrap_is_wider_than_iid_for_correlated_repeats():
    # Each group's 10 repeats always agree, so only the 12 groups carry independent information.
    rng = np.random.default_rng(0)
    winners, losers, groups = [], [], []
    for g in range(12):
        i, j = rng.choice(4, 2, replace=False)
        w, lo = (i, j) if rng.random() < 0.7 else (j, i)
        winners += [BRANDS[w]] * 10
        losers += [BRANDS[lo]] * 10
        groups += [g] * 10
    iid = bootstrap_bt(BRANDS, winners, losers, n_boot=300, seed=1)
    clustered = bootstrap_bt(BRANDS, winners, losers, n_boot=300, seed=1, groups=groups)
    assert (clustered.ci_high - clustered.ci_low).mean() > (iid.ci_high - iid.ci_low).mean()
    again = bootstrap_bt(BRANDS, winners, losers, n_boot=300, seed=1, groups=groups)
    assert np.array_equal(clustered.ci_low, again.ci_low)


# --- aggregation and report ---

from aivisibility.perception.aggregate import (  # noqa: E402
    count_cycles,
    engine_agreement,
    engine_stats,
    overlapping_pairs,
    perception_map,
)


def _rows(theta_by_engine, n_per_cell=60, a_bias=0.0, seed=0):
    """Simulated answers: BT-distributed winners, with an extra pull towards option A."""
    rng = np.random.default_rng(seed)
    rows = []
    for engine, theta in theta_by_engine.items():
        for attr in ("cheap", "fast_payouts"):
            for _ in range(n_per_cell):
                i, j = rng.choice(len(BRANDS), 2, replace=False)
                p_i = 1 / (1 + np.exp(-(theta[i] - theta[j])))
                p_i = min(1, p_i + a_bias)  # brand_first is i, so a_bias favors option A
                winner = BRANDS[i] if rng.random() < p_i else BRANDS[j]
                rows.append({"engine": engine, "attribute": attr, "context": "c", "brand_first": BRANDS[i],
                             "brand_second": BRANDS[j], "winner": winner})
    return rows


def test_perception_map_ranks_and_skips_invalid():
    theta = np.array([1.2, 0.4, -0.4, -1.2])
    rows = _rows({"openai": theta}, n_per_cell=150)
    rows.append({"engine": "openai", "attribute": "cheap", "context": "c", "brand_first": "Stripe",
                 "brand_second": "Paddle", "winner": None})
    result = perception_map(rows, BRANDS, n_boot=100, seed=1)
    res = result[("openai", "cheap")]
    assert list(np.argsort(-res.theta)) == [0, 1, 2, 3]
    assert ("Stripe", "PayPal") not in overlapping_pairs(res)  # far apart: CIs separate


def test_overlapping_pairs_lists_unrankable_brands():
    rows = _rows({"openai": np.zeros(4)}, n_per_cell=30)
    res = perception_map(rows, BRANDS, n_boot=100, seed=1)[("openai", "cheap")]
    assert len(overlapping_pairs(res)) == 6  # no real difference: nothing can be ranked


def test_engine_stats_position_bias_and_invalid_share():
    rows = _rows({"openai": np.zeros(4)}, n_per_cell=200, a_bias=0.3)
    rows += [{"engine": "openai", "attribute": "cheap", "context": "c", "brand_first": "Stripe",
              "brand_second": "Paddle", "winner": None}] * 5
    s = engine_stats(rows, n_boot=100)["openai"]
    assert s["position"]["p_first"] > 0.7 and s["invalid_share"] == pytest.approx(5 / 405)


def test_count_cycles_finds_rock_paper_scissors():
    def row(w, lo):
        return {"engine": "e", "attribute": "a", "context": "c", "brand_first": w, "brand_second": lo, "winner": w}

    rows = [row("Stripe", "Paddle")] * 3 + [row("Paddle", "Adyen")] * 3 + [row("Adyen", "Stripe")] * 3
    assert count_cycles(rows, BRANDS)[("e", "a")] == 1
    transitive = [row("Stripe", "Paddle")] * 3 + [row("Paddle", "Adyen")] * 3 + [row("Stripe", "Adyen")] * 3
    assert count_cycles(transitive, BRANDS)[("e", "a")] == 0


def test_engine_agreement_high_for_same_ranking():
    theta = np.array([1.0, 0.3, -0.3, -1.0])
    rows = _rows({"claude": theta, "openai": theta}, n_per_cell=200, seed=5)
    rho = engine_agreement(perception_map(rows, BRANDS, n_boot=50), ("claude", "openai"))
    assert all(v > 0.9 for v in rho.values())


def _load_report():
    path = Path(__file__).resolve().parents[1] / "scripts" / "perception_report.py"
    spec = importlib.util.spec_from_file_location("perception_report", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_report_runs_and_is_reproducible(tmp_db, tmp_path, monkeypatch, capsys):
    report = _load_report()
    monkeypatch.setattr(report, "OUT_FILE", tmp_path / "map.png")
    monkeypatch.setattr(report.config, "PERCEPTION_ATTRIBUTES", {"cheap": "x", "fast_payouts": "y"})
    monkeypatch.setattr(report.config, "PERCEPTION_BRANDS", BRANDS)

    report.main(None, 42, 50)
    assert "Немає відповідей" in capsys.readouterr().out  # empty DB: clear message, no crash

    run_id = db.create_pairwise_run()
    comp = build_comparisons(BRANDS, {"cheap": "x"}, ["c"], 1)[0]
    for r in _rows({"claude": np.array([1.0, 0.3, -0.3, -1.0]), "openai": np.array([0.8, 0.5, -0.2, -1.1])}):
        c = type(comp)(r["brand_first"], r["brand_second"], r["attribute"], "c", 0, "")
        db.insert_pairwise_response(run_id, r["engine"], "fake", c, "A", "A", r["winner"], 0.0, 1, None)

    report.main(None, 42, 50)
    first = capsys.readouterr().out
    report.main(None, 42, 50)
    assert capsys.readouterr().out == first
    assert (tmp_path / "map.png").stat().st_size > 0
