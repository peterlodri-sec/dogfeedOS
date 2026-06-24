# services/loop/main.py
"""dogfeedOS loop entrypoint. Reads env, probes models, loops forever."""
from __future__ import annotations
import os, time, signal, sys

import db as _db
import budget as _budget
import loop as _loop
import ralph as _ralph
import publisher as _publisher

DB_PATH           = os.environ.get('DB_PATH', '/data/dogfeed.db')
OPENROUTER_KEY    = os.environ['OPENROUTER_KEY']
OPENROUTER_MODELS = os.environ.get('OPENROUTER_MODELS', 'liquid/lfm-2.5-1.2b-instruct:free')
LOOP_TOPICS       = os.environ.get('LOOP_TOPICS', '')
LOOP_INTERVAL     = int(os.environ.get('LOOP_INTERVAL_SEC', '30'))
DAILY_CALL_LIMIT  = int(os.environ.get('DAILY_CALL_LIMIT', '200'))
DAILY_TOKEN_LIMIT = int(os.environ.get('DAILY_TOKEN_LIMIT', '50000'))
HF_TOKEN          = os.environ.get('HF_TOKEN', '')
HF_REPO           = os.environ.get('HF_REPO', '')
HF_PUSH_EVERY     = int(os.environ.get('HF_PUSH_EVERY', '50'))

_running = True

def _stop(sig, frame):
    global _running
    print('dogfeedOS: stopping cleanly...', flush=True)
    _running = False

signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


def main() -> None:
    conn = _db.get_db(DB_PATH)
    _db.init_db(conn)

    if not _db.config_get(conn, 'call_limit'):
        _db.config_set(conn, 'call_limit', str(DAILY_CALL_LIMIT))
    if not _db.config_get(conn, 'token_limit'):
        _db.config_set(conn, 'token_limit', str(DAILY_TOKEN_LIMIT))

    _db.log_event(conn, 'INFO', 'dogfeedOS starting')

    candidate_models = [m.strip() for m in OPENROUTER_MODELS.split(',') if m.strip()]
    print(f'Probing {len(candidate_models)} models...', flush=True)
    working_models = _loop.probe_models(OPENROUTER_KEY, candidate_models)
    if not working_models:
        print('ERROR: no working models. Check OPENROUTER_KEY and OPENROUTER_MODELS.', file=sys.stderr)
        sys.exit(1)
    print(f'Working: {[m.split("/")[1] for m in working_models]}', flush=True)
    _db.log_event(conn, 'INFO', f'models: {working_models}')

    state = {
        'key':        OPENROUTER_KEY,
        'models':     working_models,
        'model_idx':  0,
        'iteration':  _db.total_records(conn),
        'topics_env': LOOP_TOPICS,
        'paused':     False,
    }

    print('Loop running. Open http://localhost:8080 for the dashboard.', flush=True)

    while _running:
        paused = _db.config_get(conn, 'paused') == '1'
        state['paused'] = paused

        if paused:
            time.sleep(5)
            continue

        if not _budget.check_budget(conn):
            secs = _budget.seconds_until_midnight()
            print(f'Budget exhausted. Sleeping {secs/3600:.1f}h until midnight UTC.', flush=True)
            _db.log_event(conn, 'INFO', f'budget pause — {secs:.0f}s until reset')
            time.sleep(min(secs, 300))
            continue

        record = _loop.one_iteration(conn, state)
        if record:
            n = record['iteration']
            q = record['question'][:60]
            print(f'[{n:05d}] {q!r}', flush=True)

            if _ralph.should_reflect(conn):
                topic = _ralph.run_reflection(conn, working_models, OPENROUTER_KEY)
                if topic:
                    print(f'ralph → {topic}', flush=True)

            if HF_REPO and _publisher.should_push(conn, HF_PUSH_EVERY):
                pushed = _publisher.push_to_hf(conn, HF_REPO, HF_TOKEN)
                if pushed:
                    print(f'HF push: {pushed} records → {HF_REPO}', flush=True)

        time.sleep(LOOP_INTERVAL)

    _db.log_event(conn, 'INFO', 'dogfeedOS stopped')
    conn.close()


if __name__ == '__main__':
    main()
