# services/ui/server.py
"""dogfeedOS UI backend. One job: serve the dashboard and handle API calls."""
from __future__ import annotations
import os, sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, '/app/loop')

import db as _db
import budget as _budget
import publisher as _publisher

DB_PATH       = os.environ.get('DB_PATH', '/data/dogfeed.db')
HF_REPO       = os.environ.get('HF_REPO', '')
HF_TOKEN      = os.environ.get('HF_TOKEN', '')
HF_PUSH_EVERY = int(os.environ.get('HF_PUSH_EVERY', '50'))

STATIC = Path(__file__).parent / 'static'

app = FastAPI(title='dogfeedOS', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')


def _conn():
    conn = _db.get_db(DB_PATH)
    _db.init_db(conn)
    return conn


@app.get('/')
def dashboard():
    return FileResponse(STATIC / 'index.html')


@app.get('/setup')
def setup():
    return FileResponse(STATIC / 'setup.html')


@app.get('/api/status')
def status():
    conn = _conn()
    try:
        paused = _db.config_get(conn, 'paused') == '1'
        return {
            'loop_status':    'paused' if paused else 'running',
            'budget':         _budget.budget_status(conn),
            'total_records':  _db.total_records(conn),
            'last_pushed_at': _db.last_pushed_at(conn),
            'events':         _db.recent_events(conn, 10),
        }
    finally:
        conn.close()


@app.get('/api/records')
def records(limit: int = 20, offset: int = 0):
    conn = _conn()
    try:
        total = _db.total_records(conn)
        rows  = _db.recent_records(conn, limit + offset)[offset:offset + limit]
        return {'records': rows, 'total': total}
    finally:
        conn.close()


@app.post('/api/pause')
def pause():
    conn = _conn()
    try:
        _db.config_set(conn, 'paused', '1')
        _db.log_event(conn, 'INFO', 'loop paused via UI')
        return {'ok': True}
    finally:
        conn.close()


@app.post('/api/resume')
def resume():
    conn = _conn()
    try:
        _db.config_set(conn, 'paused', '0')
        _db.log_event(conn, 'INFO', 'loop resumed via UI')
        return {'ok': True}
    finally:
        conn.close()


class ConfigItem(BaseModel):
    key: str
    value: str


@app.post('/api/config')
def set_config(item: ConfigItem):
    conn = _conn()
    try:
        _db.config_set(conn, item.key, item.value)
        return {'ok': True}
    finally:
        conn.close()


@app.post('/api/push')
def manual_push():
    conn = _conn()
    try:
        pushed = _publisher.push_to_hf(conn, HF_REPO, HF_TOKEN)
        return {'pushed': pushed}
    finally:
        conn.close()
