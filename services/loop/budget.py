# services/loop/budget.py
"""Daily budget enforcement. One job: decide if the loop is allowed to run."""
from __future__ import annotations
import sqlite3
from datetime import date, datetime, timedelta, timezone

import db as _db


def check_budget(conn: sqlite3.Connection) -> bool:
    """Return True if the loop is allowed to make another call."""
    _db.reset_budget_if_new_day(conn)
    today = date.today().isoformat()
    b = _db.get_budget(conn, today)

    call_limit  = int(_db.config_get(conn, 'call_limit')  or b['call_limit'])
    token_limit = int(_db.config_get(conn, 'token_limit') or b['token_limit'])

    if call_limit > 0 and b['calls'] >= call_limit:
        return False
    if token_limit > 0 and b['tokens'] >= token_limit:
        return False
    return True


def use_budget(conn: sqlite3.Connection, calls: int = 1, tokens: int = 0) -> None:
    today = date.today().isoformat()
    _db.increment_budget(conn, today, calls=calls, tokens=tokens)


def budget_status(conn: sqlite3.Connection) -> dict:
    _db.reset_budget_if_new_day(conn)
    today = date.today().isoformat()
    b = _db.get_budget(conn, today)

    call_limit  = int(_db.config_get(conn, 'call_limit')  or b['call_limit'])
    token_limit = int(_db.config_get(conn, 'token_limit') or b['token_limit'])

    call_pct  = (b['calls']  / call_limit  * 100) if call_limit  > 0 else 0
    token_pct = (b['tokens'] / token_limit * 100) if token_limit > 0 else 0

    return {
        'calls_used':   b['calls'],
        'call_limit':   call_limit,
        'call_pct':     round(call_pct, 1),
        'tokens_used':  b['tokens'],
        'token_limit':  token_limit,
        'token_pct':    round(token_pct, 1),
        'secs_until_reset': seconds_until_midnight(),
        'limited':      not check_budget(conn),
    }


def seconds_until_midnight() -> float:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_midnight = midnight + timedelta(days=1)
    return (next_midnight - now).total_seconds()
