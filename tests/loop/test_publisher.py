import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../services/loop'))
from unittest.mock import patch, MagicMock
from db import get_db, init_db, write_record, unpushed_records
from publisher import should_push, push_to_hf

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

def _rec(i):
    return {'id': f'r{i}', 'question': f'Q{i}?', 'answer': f'A{i}.',
            'q_model': 'm', 'a_model': 'm', 'topic': 'ml',
            'timestamp': '2026-01-01T00:00:00Z', 'iteration': i,
            'answer_words': 2, 'question_words': 2}

def test_should_not_push_below_threshold(conn):
    for i in range(49):
        write_record(conn, _rec(i))
    assert should_push(conn, push_every=50) is False

def test_should_push_at_threshold(conn):
    for i in range(50):
        write_record(conn, _rec(i))
    assert should_push(conn, push_every=50) is True

def test_push_disabled_when_no_repo(conn):
    count = push_to_hf(conn, hf_repo='', hf_token='tok')
    assert count == 0

def test_push_calls_hf_api(conn):
    for i in range(3):
        write_record(conn, _rec(i))
    mock_api = MagicMock()
    with patch('publisher.HfApi', return_value=mock_api):
        with patch('publisher.CommitOperationAdd'):
            count = push_to_hf(conn, hf_repo='user/repo', hf_token='tok')
    assert count == 3
    assert mock_api.create_commit.called
    assert unpushed_records(conn) == []
