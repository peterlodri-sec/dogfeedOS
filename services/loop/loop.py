# services/loop/loop.py
"""Core loop iteration. One job: generate one Q&A pair per call."""
from __future__ import annotations
import hashlib, re, time, sqlite3
from datetime import datetime, timezone

import requests

import db as _db
import budget as _budget

_PII = [
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    re.compile(r'\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    re.compile(r'sk-[A-Za-z0-9]{20,}'),
    re.compile(r'hf_[A-Za-z0-9]{10,}'),
]

_FALLBACK_TOPICS = [
    'machine learning fundamentals', 'compiler design', 'distributed systems',
    'operating system internals', 'network protocols', 'data structures',
    'cryptography basics', 'database internals', 'programming language theory',
]


def pii_scrub(text: str) -> str:
    for pattern in _PII:
        text = pattern.sub('[REDACTED]', text)
    return text


def is_dup(answer: str, recent: list[dict]) -> bool:
    h = hashlib.sha256(answer.strip().lower().encode()).hexdigest()
    for r in recent:
        if hashlib.sha256(r['answer'].strip().lower().encode()).hexdigest() == h:
            return True
    return False


def pick_topic(topics_env: str, conn: sqlite3.Connection) -> str:
    if topics_env.strip():
        topics = [t.strip() for t in topics_env.split(',') if t.strip()]
        if topics:
            import random
            return random.choice(topics)
    auto = _db.config_get(conn, 'auto_topic')
    if auto:
        return auto
    import random
    return random.choice(_FALLBACK_TOPICS)


def probe_models(key: str, models: list[str]) -> list[str]:
    working = []
    for model in models:
        try:
            r = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                json={'model': model, 'messages': [{'role': 'user', 'content': 'ping'}], 'max_tokens': 5},
                timeout=20,
            )
            r.raise_for_status()
            if r.json().get('choices'):
                working.append(model)
        except Exception:
            pass
    return working


def ask(prompt: str, model: str, key: str, max_tokens: int = 512) -> str | None:
    try:
        r = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {key}',
                'HTTP-Referer': 'https://github.com/peterlodri-sec/dogfeedOS',
                'Content-Type': 'application/json',
            },
            json={'model': model, 'messages': [{'role': 'user', 'content': prompt}],
                  'max_tokens': max_tokens, 'temperature': 0.7},
            timeout=30,
        )
        r.raise_for_status()
        choices = r.json().get('choices')
        if not choices:
            return None
        return choices[0]['message']['content'].strip()
    except requests.HTTPError as e:
        if e.response.status_code == 429:
            time.sleep(10)
        return None
    except Exception:
        return None


def one_iteration(conn: sqlite3.Connection, state: dict) -> dict | None:
    if state.get('paused'):
        return None
    if not _budget.check_budget(conn):
        _db.log_event(conn, 'INFO', 'budget exhausted — sleeping')
        return None
    models = state['models']
    if not models:
        _db.log_event(conn, 'ERROR', 'no working models')
        return None
    key        = state['key']
    topics_env = state.get('topics_env', '')
    idx        = state['model_idx']
    q_model = models[idx % len(models)]
    a_model = models[(idx + 1) % len(models)]
    topic   = pick_topic(topics_env, conn)
    q_prompt = (
        f'Ask the most important first question about: {topic}\n'
        f'Target a specific mechanism, concept, or tradeoff — not a meta-question.\n'
        f'Just the question, nothing else.'
    )
    question = ask(q_prompt, q_model, key, max_tokens=128)
    if not question:
        return None
    a_prompt = (
        f'Give a clear, accurate, and thorough answer.\n'
        f'If uncertain about anything, say so explicitly.\n\n'
        f'Question: {question}'
    )
    answer = ask(a_prompt, a_model, key, max_tokens=600)
    if not answer:
        return None
    question = pii_scrub(question)
    answer   = pii_scrub(answer)
    recent   = _db.recent_records(conn, 50)
    if is_dup(answer, recent):
        return None
    n   = state['iteration']
    ts  = datetime.now(timezone.utc).isoformat()
    record = {
        'id': f'loop-{n:05d}', 'question': question, 'answer': answer,
        'q_model': q_model, 'a_model': a_model, 'topic': topic,
        'timestamp': ts, 'iteration': n,
        'answer_words': len(answer.split()), 'question_words': len(question.split()),
    }
    _db.write_record(conn, record)
    _budget.use_budget(conn, calls=2, tokens=len(question.split()) + len(answer.split()))
    state['model_idx']  = idx + 1
    state['iteration']  = n + 1
    return record
