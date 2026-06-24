import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/loop'))
from unittest.mock import patch
from db import get_db, init_db, write_record, config_get
from ralph import run_reflection, should_reflect

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

def _make_record(i):
    return {'id': f'r{i}', 'question': f'Q{i}?', 'answer': f'A{i}.', 'q_model': 'm',
            'a_model': 'm', 'topic': 'ml', 'timestamp': '2026-01-01T00:00:00Z',
            'iteration': i, 'answer_words': 2, 'question_words': 2}

def test_should_not_reflect_before_50(conn):
    for i in range(49):
        write_record(conn, _make_record(i))
    assert should_reflect(conn) is False

def test_should_reflect_at_50(conn):
    for i in range(50):
        write_record(conn, _make_record(i))
    assert should_reflect(conn) is True

def test_run_reflection_stores_topic(conn):
    for i in range(50):
        write_record(conn, _make_record(i))
    with patch('ralph.ask', return_value='quantum computing'):
        topic = run_reflection(conn, ['model-a'], 'fake-key')
    assert topic == 'quantum computing'
    assert config_get(conn, 'auto_topic') == 'quantum computing'

def test_run_reflection_returns_none_on_failure(conn):
    for i in range(50):
        write_record(conn, _make_record(i))
    with patch('ralph.ask', return_value=None):
        topic = run_reflection(conn, ['model-a'], 'fake-key')
    assert topic is None
