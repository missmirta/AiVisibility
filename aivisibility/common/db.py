"""SQLite storage: schema, connection helper, and query loading.

Schema: queries -> runs -> responses -> mentions (query -> run -> response ->
detected mentions, per docs/weeks/week2.md). `mentions` is created here but
stays empty until week 3 (detection logic is out of scope for week 2).
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

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
    method TEXT NOT NULL,
    created_at TEXT
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


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring a pre-existing DB up to the current schema. `CREATE TABLE IF NOT
    EXISTS` never alters an existing table, so new columns are added here.
    Rows written before the column existed keep created_at = NULL."""
    mention_cols = {row["name"] for row in conn.execute("PRAGMA table_info(mentions)")}
    if "created_at" not in mention_cols:
        conn.execute("ALTER TABLE mentions ADD COLUMN created_at TEXT")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


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


def get_run_ids() -> list[int]:
    with connect() as conn:
        return [row["id"] for row in conn.execute("SELECT id FROM runs ORDER BY id").fetchall()]


def create_run(notes: str | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (started_at, notes) VALUES (?, ?)",
            (datetime.now(UTC).isoformat(), notes),
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
                datetime.now(UTC).isoformat(),
            ),
        )
        return cur.lastrowid


def get_responses_with_brand(
    run_id: int | None = None, since: str | None = None, until: str | None = None
) -> list[sqlite3.Row]:
    """responses joined with their query's brand — what week 3 analysis
    reads to know which brand's candidate dictionary applies to each
    response. Pass run_id to scope to one run (for the report), or omit for
    all responses (for detection). Pass `since` (an ISO-8601 UTC string, the
    format `created_at` is stored in) to keep only responses collected at or
    after that moment, and `until` to keep only those collected before it —
    a time window across runs."""
    sql = """
        SELECT r.id AS response_id, r.run_id, r.engine, r.raw_text, r.error,
               q.brand AS subject_brand, q.id AS query_id
        FROM responses r
        JOIN queries q ON q.id = r.query_id
    """
    where: list[str] = []
    params: list = []
    if run_id is not None:
        where.append("r.run_id = ?")
        params.append(run_id)
    if since is not None:
        where.append("r.created_at >= ?")
        params.append(since)
    if until is not None:
        where.append("r.created_at < ?")
        params.append(until)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.id"
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def replace_mentions_for_response(
    response_id: int, brands_mentioned: list[str], method: str
) -> None:
    """Idempotent: drops any existing `mentions` rows for this response_id
    before inserting the fresh detection result, so rerunning after a
    detection-logic change never accumulates duplicates."""
    with connect() as conn:
        conn.execute("DELETE FROM mentions WHERE response_id = ?", (response_id,))
        if brands_mentioned:
            now = datetime.now(UTC).isoformat()
            conn.executemany(
                "INSERT INTO mentions (response_id, brand_mentioned, method, created_at) "
                "VALUES (?, ?, ?, ?)",
                [(response_id, brand, method, now) for brand in brands_mentioned],
            )


def get_mentions_for_responses(response_ids: list[int]) -> dict[int, set[str]]:
    """response_id -> set of brand_mentioned, for the given response_ids."""
    result: dict[int, set[str]] = {rid: set() for rid in response_ids}
    if not response_ids:
        return result
    placeholders = ",".join("?" * len(response_ids))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT response_id, brand_mentioned FROM mentions WHERE response_id IN ({placeholders})",
            response_ids,
        ).fetchall()
    for row in rows:
        result[row["response_id"]].add(row["brand_mentioned"])
    return result
