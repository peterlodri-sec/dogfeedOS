import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/ui'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/loop'))
import pytest

os.environ.setdefault('DB_PATH', tempfile.mktemp(suffix='.db'))
os.environ.setdefault('HF_REPO', '')
os.environ.setdefault('HF_TOKEN', '')
os.environ.setdefault('HF_PUSH_EVERY', '50')

from server import app
from db import get_db, init_db
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def init_test_db():
    path = os.environ['DB_PATH']
    conn = get_db(path)
    init_db(conn)
    conn.close()
    yield
    if os.path.exists(path):
        os.unlink(path)

client = TestClient(app)

def test_status_ok():
    r = client.get('/api/status')
    assert r.status_code == 200
    data = r.json()
    assert 'budget' in data
    assert 'total_records' in data
    assert 'loop_status' in data

def test_records_empty():
    r = client.get('/api/records?limit=10&offset=0')
    assert r.status_code == 200
    assert r.json()['records'] == []
    assert r.json()['total'] == 0

def test_pause_resume():
    r = client.post('/api/pause')
    assert r.status_code == 200
    assert r.json()['ok'] is True
    r = client.post('/api/resume')
    assert r.status_code == 200
    assert r.json()['ok'] is True

def test_config_set():
    r = client.post('/api/config', json={'key': 'call_limit', 'value': '100'})
    assert r.status_code == 200
    assert r.json()['ok'] is True

def test_manual_push_no_repo():
    r = client.post('/api/push')
    assert r.status_code == 200
    assert r.json()['pushed'] == 0
