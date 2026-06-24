# services/loop/db.py
"""All SQLite operations for dogfeedOS. One job: read/write the shared database."""
from __future__ import annotations
import sqlite3
from datetime import date, datetime, timezone


def get_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _rows_to_dicts(cursor: sqlite3.Cursor, rows: list) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in rows]


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS records (
            id             TEXT PRIMARY KEY,
            question       TEXT NOT NULL,
            answer         TEXT NOT NULL,
            q_model        TEXT,
            a_model        TEXT,
            topic          TEXT,
            timestamp      TEXT NOT NULL,
            iteration      INTEGER,
            answer_words   INTEGER,
            question_words INTEGER,
            pushed_to_hf   INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS budget (
            date        TEXT PRIMARY KEY,
            calls       INTEGER DEFAULT 0,
            tokens      INTEGER DEFAULT 0,
            call_limit  INTEGER DEFAULT 200,
            token_limit INTEGER DEFAULT 50000
        );
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts      TEXT NOT NULL,
            level   TEXT NOT NULL,
            message TEXT NOT NULL
        );
    """)
    conn.commit()


def write_record(conn: sqlite3.Connection, record: dict) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO records
          (id, question, answer, q_model, a_model, topic, timestamp,
           iteration, answer_words, question_words, pushed_to_hf)
        VALUES (:id, :question, :answer, :q_model, :a_model, :topic,
                :timestamp, :iteration, :answer_words, :question_words, 0)
    """, record)
    conn.commit()


def recent_records(conn: sqlite3.Connection, n: int = 50) -> list[dict]:
    cur = conn.execute("SELECT * FROM records ORDER BY timestamp DESC LIMIT ?", (n,))
    return _rows_to_dicts(cur, cur.fetchall())


def unpushed_records(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM records WHERE pushed_to_hf = 0 ORDER BY timestamp ASC")
    return _rows_to_dicts(cur, cur.fetchall())


def mark_pushed(conn: sqlite3.Connection, ids: list[str]) -> None:
    conn.executemany(
        "UPDATE records SET pushed_to_hf = 1 WHERE id = ?",
        [(i,) for i in ids]
    )
    conn.commit()


def get_budget(conn: sqlite3.Connection, date_str: str) -> dict:
    cur = conn.execute("SELECT * FROM budget WHERE date = ?", (date_str,))
    row = cur.fetchone()
    if row:
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    return {'date': date_str, 'calls': 0, 'tokens': 0, 'call_limit': 200, 'token_limit': 50000}


def increment_budget(conn: sqlite3.Connection, date_str: str, calls: int, tokens: int) -> None:
    conn.execute("""
        INSERT INTO budget (date, calls, tokens) VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
          calls  = calls  + excluded.calls,
          tokens = tokens + excluded.tokens
    """, (date_str, calls, tokens))
    conn.commit()


def reset_budget_if_new_day(conn: sqlite3.Connection) -> None:
    today = date.today().isoformat()
    conn.execute("DELETE FROM budget WHERE date != ?", (today,))
    conn.commit()


def total_records(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]


def last_pushed_at(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT timestamp FROM records WHERE pushed_to_hf=1 ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def config_get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def config_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()


def log_event(conn: sqlite3.Connection, level: str, message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO events (ts, level, message) VALUES (?, ?, ?)", (ts, level, message)
    )
    conn.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 100)")
    conn.commit()


def recent_events(conn: sqlite3.Connection, n: int = 20) -> list[dict]:
    cur = conn.execute("SELECT ts, level, message FROM events ORDER BY id DESC LIMIT ?", (n,))
    return _rows_to_dicts(cur, cur.fetchall())
