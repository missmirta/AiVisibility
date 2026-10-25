import json

import numpy as np
import pytest

from aivisibility.analysis import adaptive_sampling
from aivisibility.common import config, db
from aivisibility.perception.pairs import Comparison
from aivisibility.reporting import dashboard_data
from aivisibility.reporting.dashboard_data import build_dashboard_data, perception_section

BRANDS = ["Stripe", "Paddle", "Adyen", "PayPal"]


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    db.init_db()


def _fill_pairwise(seed=0, n=120):
    """Simulated answers where earlier brands in BRANDS are stronger."""
    theta = np.array([1.0, 0.3, -0.3, -1.0])
    rng = np.random.default_rng(seed)
    run_id = db.create_pairwise_run()
    for k in range(n):
        i, j = rng.choice(4, 2, replace=False)
        winner = BRANDS[i] if rng.random() < 1 / (1 + np.exp(-(theta[i] - theta[j]))) else BRANDS[j]
        c = Comparison(BRANDS[i], BRANDS[j], "cheap", f"ctx{k % 2}", k, "")
        db.insert_pairwise_response(run_id, "claude", "fake", c, "A", "A", winner, 0.0, 1, None)
    return run_id


def test_perception_section_empty_db_is_marked_unavailable(tmp_db):
    assert perception_section(None, seed=1, n_boot=20) == {"available": False}


def test_perception_section_has_ci_for_every_brand_and_is_reproducible(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "PERCEPTION_BRANDS", BRANDS)
    _fill_pairwise()
    first = perception_section(None, seed=7, n_boot=50)
    assert first == perception_section(None, seed=7, n_boot=50)
    cell = first["cells"][0]
    assert cell["engine"] == "claude" and cell["attribute"] == "cheap"
    assert len(cell["brands"]) == 4
    for b in cell["brands"]:
        assert b["ci_low"] <= b["theta"] <= b["ci_high"]
    assert sorted(b["rank"] for b in cell["brands"]) == [1, 2, 3, 4]
    assert first["engine_stats"]["claude"]["n"] == 120


def test_build_dashboard_data_is_strict_json_with_meta(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "PERCEPTION_BRANDS", BRANDS)
    monkeypatch.setattr(dashboard_data, "REAL_QUERIES_FILE", config.QUERIES_DIR / "no_such_file.json")
    _fill_pairwise()
    data = build_dashboard_data(seed=3, n_resamples=20, n_boot=20)
    text = json.dumps(data, allow_nan=False)  # raises on NaN/inf
    meta = json.loads(text)["meta"]
    assert meta["seed"] == 3 and meta["schema_version"] == dashboard_data.SCHEMA_VERSION
    assert meta["not_exported"] == dashboard_data.NOT_EXPORTED


def test_num_maps_non_finite_to_none():
    assert dashboard_data._num(float("nan")) is None
    assert dashboard_data._num(0.5) == 0.5


def test_representativeness_section_unavailable_without_real_queries(tmp_db, monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_data, "REAL_QUERIES_FILE", tmp_path / "missing.json")
    assert dashboard_data.representativeness_section(seed=1, permutations=10) == {"available": False}


def test_representativeness_section_has_ci_and_is_reproducible(monkeypatch, tmp_path):
    rng = np.random.default_rng(0)
    syn_texts = [f"syn {i}" for i in range(30)]
    real_texts = [f"real {i} vs x" for i in range(40)]  # "vs" so the choice-question subset is non-empty
    real_file = tmp_path / "real.json"
    real_file.write_text(json.dumps([{"text": t} for t in real_texts]), encoding="utf-8")
    emb = {t: rng.normal(loc=0 if t.startswith("syn") else 2, scale=0.3, size=4) for t in syn_texts + real_texts}
    values = [bool(i % 3 == 0) for i in range(30)]
    monkeypatch.setattr(dashboard_data, "REAL_QUERIES_FILE", real_file)
    monkeypatch.setattr(db, "get_all_queries", lambda: [{"id": i, "text": t} for i, t in enumerate(syn_texts)])
    monkeypatch.setattr(
        dashboard_data, "weighted_mention_vectors",
        lambda qw: {("Stripe", "claude", "Adyen"): (values, [qw.get(i, 0.0) for i in range(30)])},
    )

    def run():
        return dashboard_data.representativeness_section(
            seed=5, permutations=20, embed=lambda texts: np.array([emb[t] for t in texts]),
        )

    first = run()
    assert first == run()
    assert first["two_sample"]["all_real"]["auc"] > 0.9  # clearly different by construction
    m = first["mentions"][0]
    for side in ("unweighted", "weighted"):
        assert m[side]["ci_low"] <= m[side]["rate"] <= m[side]["ci_high"]
    assert m["sensitivity"]["verdict"] in {"no_change", "stable_sign", "mixed_sign"}
    assert abs(sum(c["p_synthetic"] for c in first["clusters"]["items"]) - 1) < 1e-9
    json.dumps(first, allow_nan=False)


def _fake_arms():
    pool = [{"A": i % 3 == 0, "B": i % 5 == 0} for i in range(30)]
    return [
        adaptive_sampling.BanditArm("Brand1", "claude", ["A", "B"], pool),
        adaptive_sampling.BanditArm("Brand2", "openai", ["A", "B"], pool),
    ]


def test_adaptive_sampling_section_unavailable_without_responses(tmp_db):
    assert dashboard_data.adaptive_sampling_section(seed=1, n_resamples=10) == {"available": False}


def test_adaptive_sampling_section_has_ci_and_is_reproducible(monkeypatch):
    monkeypatch.setattr(adaptive_sampling, "build_arms", _fake_arms)

    def run():
        return dashboard_data.adaptive_sampling_section(seed=4, n_resamples=20, budgets=[8, 16, 32], n_repeats=3)

    first = run()
    assert first == run()
    assert first["n_arms"] == 2 and first["n_entities"] == 4
    for kind in ("mean", "max"):
        savings = first["fixed_budget"][kind]["savings_pct"]
        assert savings["ci_low"] <= savings["ci_high"]
        assert len(first["fixed_budget"][kind]["curves"]["uniform"]) == 3
    assert "distinguishable_from_zero" in first["full_convergence"]["adaptive_saving_pct"]
    json.dumps(first, allow_nan=False)


def _write_csv(path, header, rows):
    path.write_text("\n".join([",".join(header)] + [",".join(r) for r in rows]) + "\n", encoding="utf-8")


def test_stance_section_counts_real_snippets_with_ci_and_skips_synthetic(monkeypatch, tmp_path):
    labels_file = tmp_path / "stance.csv"
    rows = [(f"t{i}", "recommended" if i % 2 else "neutral", "Stripe", str(i % 4 + 1)) for i in range(8)]
    rows.append(("synthetic", "negative", "Stripe", "100001"))  # id not in the DB: must be dropped
    rows.append(("lone", "negative", "Paddle", "5"))
    _write_csv(labels_file, ["text", "label", "brand", "response_id"], rows)
    monkeypatch.setattr(config, "STANCE_LABELS_FILE", labels_file)
    monkeypatch.setattr(dashboard_data, "GOLD_FILE", tmp_path / "missing_gold.csv")
    monkeypatch.setattr(
        db, "get_responses_with_brand",
        lambda: [{"response_id": i, "subject_brand": "Stripe", "engine": "claude"} for i in range(1, 6)],
    )

    first = dashboard_data.stance_section(seed=2, n_resamples=50)
    assert first == dashboard_data.stance_section(seed=2, n_resamples=50)
    by_brand = {i["brand"]: i for i in first["items"]}
    stripe, paddle = by_brand["Stripe"], by_brand["Paddle"]
    assert stripe["n_snippets"] == 8 and stripe["n_responses"] == 4  # synthetic row not counted
    assert abs(sum(s["rate"] for s in stripe["shares"].values()) - 1) < 1e-9
    for s in stripe["shares"].values():
        assert s["ci_low"] <= s["rate"] <= s["ci_high"]
    assert paddle["ci_available"] is False and paddle["shares"]["negative"]["ci_low"] is None
    assert first["teacher_agreement"] == {"available": False}
    json.dumps(first, allow_nan=False)


def test_stance_section_unavailable_without_labels_file(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STANCE_LABELS_FILE", tmp_path / "missing.csv")
    assert dashboard_data.stance_section(seed=1, n_resamples=10) == {"available": False}


def test_teacher_agreement_kappa_has_ci(monkeypatch, tmp_path):
    gold, key = tmp_path / "gold.csv", tmp_path / "key.csv"
    names = ["recommended", "neutral", "negative"]
    _write_csv(gold, ["row_id", "human_label"], [(str(i), names[i % 3]) for i in range(30)])
    # Claude agrees on all rows except every 5th
    _write_csv(key, ["row_id", "claude_label"], [(str(i), names[(i + (i % 5 == 0)) % 3]) for i in range(30)])
    monkeypatch.setattr(dashboard_data, "GOLD_FILE", gold)
    monkeypatch.setattr(dashboard_data, "GOLD_TEACHER_FILE", key)
    out = dashboard_data._teacher_agreement(seed=1, n_resamples=50)
    assert out["n"] == 30 and 0 < out["kappa"] < 1
    assert out["kappa_ci_low"] <= out["kappa"] <= out["kappa_ci_high"]
