import sqlite3, tempfile, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/loop'))

import pytest
from db import init_db, get_db, write_record, recent_records, get_budget, increment_budget, config_get, config_set, log_event

@pytest.fixture
def conn():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    conn = get_db(path)
    init_db(conn)
    yield conn
    conn.close()
    os.unlink(path)

def test_init_creates_tables(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {'records', 'budget', 'config', 'events'} <= tables

def test_write_and_read_record(conn):
    record = {
        'id': 'loop-00001', 'question': 'What is a compiler?',
        'answer': 'A compiler translates source code.', 'q_model': 'gpt-oss',
        'a_model': 'lfm', 'topic': 'compilers', 'timestamp': '2026-01-01T00:00:00Z',
        'iteration': 1, 'answer_words': 5, 'question_words': 4,
    }
    write_record(conn, record)
    rows = recent_records(conn, 10)
    assert len(rows) == 1
    assert rows[0]['id'] == 'loop-00001'
    assert rows[0]['pushed_to_hf'] == 0

def test_budget_increment(conn):
    from datetime import date
    today = date.today().isoformat()
    increment_budget(conn, today, calls=1, tokens=100)
    b = get_budget(conn, today)
    assert b['calls'] == 1
    assert b['tokens'] == 100
    assert b['call_limit'] == 200
    assert b['token_limit'] == 50000

def test_config_roundtrip(conn):
    config_set(conn, 'auto_topic', 'neural networks')
    assert config_get(conn, 'auto_topic') == 'neural networks'

def test_config_missing_returns_none(conn):
    assert config_get(conn, 'nonexistent') is None

def test_log_event(conn):
    log_event(conn, 'INFO', 'loop started')
    rows = conn.execute("SELECT level, message FROM events").fetchall()
    assert rows[0] == ('INFO', 'loop started')
