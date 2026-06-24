import sqlite3, tempfile, os, sys
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/loop'))
from db import get_db, init_db
from budget import check_budget, use_budget, budget_status, seconds_until_midnight

import pytest

@pytest.fixture
def conn():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    conn = get_db(path)
    init_db(conn)
    yield conn
    conn.close()
    os.unlink(path)

def test_check_budget_ok_when_empty(conn):
    assert check_budget(conn) is True

def test_check_budget_fails_when_calls_exhausted(conn):
    today = date.today().isoformat()
    from db import increment_budget
    increment_budget(conn, today, calls=200, tokens=0)
    assert check_budget(conn) is False

def test_check_budget_fails_when_tokens_exhausted(conn):
    today = date.today().isoformat()
    from db import increment_budget
    increment_budget(conn, today, calls=0, tokens=50000)
    assert check_budget(conn) is False

def test_check_budget_unlimited_when_limit_zero(conn):
    from db import config_set
    config_set(conn, 'call_limit', '0')
    config_set(conn, 'token_limit', '0')
    today = date.today().isoformat()
    from db import increment_budget
    increment_budget(conn, today, calls=9999, tokens=9999999)
    assert check_budget(conn) is True

def test_budget_status_shape(conn):
    status = budget_status(conn)
    assert 'calls_used' in status
    assert 'call_limit' in status
    assert 'tokens_used' in status
    assert 'token_limit' in status
    assert 'call_pct' in status
    assert 'secs_until_reset' in status

def test_seconds_until_midnight_positive():
    s = seconds_until_midnight()
    assert 0 < s <= 86400
