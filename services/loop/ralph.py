# services/loop/ralph.py
"""Ralph reflection pass. One job: pick the next topic from what the loop already knows."""
from __future__ import annotations
import sqlite3

import db as _db
from loop import ask

_REFLECT_EVERY = 50


def should_reflect(conn: sqlite3.Connection) -> bool:
    total = _db.total_records(conn)
    return total > 0 and total % _REFLECT_EVERY == 0


def run_reflection(conn: sqlite3.Connection, models: list[str], key: str) -> str | None:
    if not models:
        return None
    recent = _db.recent_records(conn, 50)
    if not recent:
        return None
    topics_seen = list({r['topic'] for r in recent if r.get('topic')})
    qa_sample = '\n'.join(f'Q: {r["question"][:100]}' for r in recent[:10])
    prompt = (
        f'A data loop has been generating Q&A pairs. '
        f'Recent topics: {", ".join(topics_seen)}.\n\n'
        f'Sample questions:\n{qa_sample}\n\n'
        f'What ONE specific topic should the loop explore next that it has NOT covered yet? '
        f'Reply with only the topic name, nothing else.'
    )
    model = models[0]
    topic = ask(prompt, model, key, max_tokens=32)
    if not topic:
        return None
    topic = topic.strip().strip('"').strip("'")
    _db.config_set(conn, 'auto_topic', topic)
    _db.log_event(conn, 'INFO', f'ralph: next topic → {topic}')
    return topic
