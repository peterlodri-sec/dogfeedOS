# services/loop/publisher.py
"""HuggingFace dataset push. One job: upload unpushed records as JSONL."""
from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone

from huggingface_hub import HfApi, CommitOperationAdd

import db as _db


def should_push(conn: sqlite3.Connection, push_every: int) -> bool:
    if push_every <= 0:
        return False
    unpushed = len(_db.unpushed_records(conn))
    return unpushed >= push_every


def push_to_hf(conn: sqlite3.Connection, hf_repo: str, hf_token: str) -> int:
    if not hf_repo or not hf_token:
        return 0
    records = _db.unpushed_records(conn)
    if not records:
        return 0
    ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    fname = f'dogfeed-loop-{ts}.jsonl'
    content = '\n'.join(json.dumps(r) for r in records) + '\n'
    api = HfApi()
    try:
        api.create_commit(
            repo_id=hf_repo, repo_type='dataset',
            operations=[CommitOperationAdd(path_in_repo=fname, path_or_fileobj=content.encode())],
            commit_message=f'dogfeedOS: {len(records)} records [{ts}]',
            token=hf_token,
        )
        _db.mark_pushed(conn, [r['id'] for r in records])
        _db.log_event(conn, 'INFO', f'pushed {len(records)} records → {hf_repo}')
        return len(records)
    except Exception as e:
        _db.log_event(conn, 'ERROR', f'HF push failed: {e}')
        return 0
