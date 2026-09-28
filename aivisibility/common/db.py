"""SQLite storage: schema, connection helper, and query loading.

Schema: queries -> runs -> responses -> mentions (query -> run -> response ->
detected mentions, per docs/weeks/week2.md). `mentions` is created here but
stays empty until week 3 (detection logic is out of scope for week 2).
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH, QUERIES_FILE

_SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL,
    intent TEXT NOT NULL,
    text TEXT NOT NULL,
    mentions_competitors TEXT NOT NULL DEFAULT '[]',
    UNIQUE(brand, text)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    query_id INTEGER NOT NULL REFERENCES queries(id),
    engine TEXT NOT NULL CHECK (engine IN ('claude', 'openai')),
    model TEXT NOT NULL,
    raw_text TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost_usd REAL,
    latency_ms INTEGER,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES responses(id),
    brand_mentioned TEXT NOT NULL,
    method TEXT NOT NULL
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


def load_queries_from_json() -> int:
    """Idempotently load data/queries/queries.json into the queries table.
    Returns the number of newly inserted rows (duplicates are skipped)."""
    data = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    with connect() as conn:
        cur = conn.executemany(
            "INSERT OR IGNORE INTO queries (brand, intent, text, mentions_competitors) "
            "VALUES (:brand, :intent, :text, :mentions_competitors)",
            [
                {
                    "brand": q["brand"],
                    "intent": q["intent"],
                    "text": q["text"],
                    "mentions_competitors": json.dumps(q["mentions_competitors"]),
                }
                for q in data
            ],
        )
        return cur.rowcount


def get_all_queries() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM queries ORDER BY id").fetchall()


def create_run(notes: str | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (started_at, notes) VALUES (?, ?)",
            (datetime.now(timezone.utc).isoformat(), notes),
        )
        return cur.lastrowid


def insert_response(
    run_id: int,
    query_id: int,
    engine: str,
    model: str,
    raw_text: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cost_usd: float | None,
    latency_ms: int,
    error: str | None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO responses
                (run_id, query_id, engine, model, raw_text, prompt_tokens,
                 completion_tokens, cost_usd, latency_ms, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                query_id,
                engine,
                model,
                raw_text,
                prompt_tokens,
                completion_tokens,
                cost_usd,
                latency_ms,
                error,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.lastrowid
