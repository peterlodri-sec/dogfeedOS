import sys, os, sqlite3, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/loop'))
from unittest.mock import patch, MagicMock
from db import get_db, init_db
from loop import probe_models, pii_scrub, is_dup, pick_topic

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

def test_pii_scrub_email():
    assert 'test@example.com' not in pii_scrub('contact test@example.com now')

def test_pii_scrub_phone():
    assert '+1-555-555-5555' not in pii_scrub('call +1-555-555-5555')

def test_pii_scrub_preserves_normal_text():
    text = 'Gradient descent minimizes loss functions.'
    assert pii_scrub(text) == text

def test_is_dup_detects_identical(conn):
    from db import write_record
    record = {'id': 'r1', 'question': 'What is X?', 'answer': 'X is Y.',
              'q_model': 'm', 'a_model': 'm', 'topic': 't',
              'timestamp': '2026-01-01T00:00:00Z', 'iteration': 1,
              'answer_words': 3, 'question_words': 3}
    write_record(conn, record)
    from db import recent_records
    recent = recent_records(conn, 10)
    assert is_dup('X is Y.', recent) is True

def test_is_dup_allows_novel(conn):
    assert is_dup('Completely novel answer about quantum computing.', []) is False

def test_pick_topic_from_env(conn):
    topic = pick_topic('compilers,ML,databases', conn)
    assert topic in ('compilers', 'ML', 'databases')

def test_pick_topic_from_auto_config(conn):
    from db import config_set
    config_set(conn, 'auto_topic', 'neural fields')
    topic = pick_topic('', conn)
    assert topic == 'neural fields'

def test_pick_topic_fallback_when_empty(conn):
    topic = pick_topic('', conn)
    assert isinstance(topic, str)
    assert len(topic) > 0

def test_probe_models_removes_non_responding():
    def fake_post(*a, **kw):
        m = MagicMock()
        m.raise_for_status.side_effect = Exception('unreachable')
        return m
    with patch('requests.post', side_effect=fake_post):
        result = probe_models('fake-key', ['bad-model-1', 'bad-model-2'])
    assert result == []
