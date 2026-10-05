from datetime import UTC, datetime, timedelta

import pytest

from aivisibility.analysis.report import compute_mention_rates
from aivisibility.common import db

NOW = datetime(2026, 10, 5, tzinfo=UTC)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    db.init_db()
    with db.connect() as conn:
        conn.execute("INSERT INTO queries (brand, intent, text) VALUES ('Stripe', 'x', 'q1')")
    return tmp_path


def _add_response(days_ago: float, mentioned: bool) -> None:
    run_id = db.create_run()
    rid = db.insert_response(run_id, 1, "claude", "m", "text", 1, 1, 0.0, 1, None)
    created = (NOW - timedelta(days=days_ago)).isoformat()
    with db.connect() as conn:
        conn.execute("UPDATE responses SET created_at = ? WHERE id = ?", (created, rid))
    db.replace_mentions_for_response(rid, ["Stripe"] if mentioned else [], "test")


def _stripe_row(rows):
    return next(r for r in rows if r.subject_brand == "Stripe" and r.mentioned_entity == "Stripe")


def test_window_excludes_old_responses(tmp_db):
    for _ in range(5):
        _add_response(days_ago=60, mentioned=True)  # old: always mentioned
    for _ in range(5):
        _add_response(days_ago=1, mentioned=False)  # recent: never mentioned

    all_time = _stripe_row(compute_mention_rates(n_resamples=200, seed=0, now=NOW))
    windowed = _stripe_row(
        compute_mention_rates(n_resamples=200, seed=0, window_days=30, now=NOW)
    )

    assert all_time.n == 10
    assert all_time.point == pytest.approx(0.5)
    assert windowed.n == 5
    assert windowed.point == 0.0


def test_preceding_window_via_shifted_now(tmp_db):
    _add_response(days_ago=45, mentioned=True)  # in [60, 30) days ago
    _add_response(days_ago=1, mentioned=False)  # in the current window

    previous = _stripe_row(
        compute_mention_rates(
            n_resamples=200, seed=0, window_days=30, now=NOW - timedelta(days=30)
        )
    )

    assert previous.n == 1
    assert previous.point == 1.0
