import pytest

from aivisibility.common import db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    db.init_db()
    with db.connect() as conn:
        for text in ("a", "b", "c"):
            conn.execute("INSERT INTO queries (brand, intent, text) VALUES ('Stripe', 'x', ?)", (text,))


def test_get_queries_from_keeps_only_ids_at_or_above_min(tmp_db):
    assert [q["text"] for q in db.get_queries_from(2)] == ["b", "c"]


def test_get_queries_from_one_returns_everything(tmp_db):
    assert len(db.get_queries_from(1)) == 3
