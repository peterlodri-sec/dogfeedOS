# dogfeedOS

A self-improving Q&A data loop for Raspberry Pi 3/4.  
Runs two Docker containers. Generates data. Teaches itself what to ask next.

**Zero config required to start. Three minutes from clone to running loop.**

---

## Quick start

```bash
git clone https://github.com/peterlodri-sec/dogfeedOS
cd dogfeedOS
cp .env.example .env
# Edit .env — add your OPENROUTER_KEY (free at openrouter.ai)
docker compose up
```

Open **http://localhost:8080/setup** to configure topics, budget, and HuggingFace push.  
Then open **http://localhost:8080** to watch the live feed.

---

## What it does

Each loop iteration:
1. Picks a topic (from your config, or self-generates via the ralph pass)
2. Asks a free LLM: *"What is the most important question about this topic?"*
3. Asks a second free LLM to answer it
4. Scrubs PII, deduplicates, saves to SQLite
5. Every 50 records: reflects on what was generated and picks the next topic
6. Optionally pushes to your HuggingFace dataset

The loop runs forever. Budget limits prevent runaway API usage (default: 200 calls/day).

---

## Requirements

- Docker + Docker Compose (any platform)
- A free [OpenRouter](https://openrouter.ai) API key
- Optional: a HuggingFace account for dataset publishing

**Tested on:** Raspberry Pi 3B+ (1GB), Raspberry Pi 4 (4GB), macOS, Linux x86_64.

---

## Configuration

All config is in `.env`. Copy `.env.example` and edit:

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_KEY` | required | Free at openrouter.ai |
| `LOOP_TOPICS` | blank (self-steer) | Comma-separated topics |
| `LOOP_INTERVAL_SEC` | 30 | Seconds between iterations |
| `DAILY_CALL_LIMIT` | 200 | Max API calls/day (0 = unlimited) |
| `DAILY_TOKEN_LIMIT` | 50000 | Max tokens/day (0 = unlimited) |
| `HF_TOKEN` | blank | HuggingFace write token |
| `HF_REPO` | blank | e.g. `username/my-dataset` |
| `HF_PUSH_EVERY` | 50 | Push after every N records |
| `UI_PORT` | 8080 | Dashboard port |
| `OPENROUTER_MODELS` | see .env.example | Comma-separated model IDs |

Changes from the `/setup` wizard take effect on the next iteration (no restart needed).

---

## Architecture

```
┌─────────────────┐    SQLite    ┌─────────────────┐
│  dogfeed        │◄────────────►│  dogfeedui      │
│  loop engine    │  /data/      │  FastAPI + HTML  │
│  budget tracker │  dogfeed.db  │  port 8080       │
│  ralph pass     │              │  /setup wizard   │
│  HF publisher   │              │  live dashboard  │
└─────────────────┘              └─────────────────┘
```

Two containers. One shared volume. The loop writes; the UI reads.

---

## Contributing

```bash
pip install pytest requests fastapi uvicorn httpx huggingface-hub
python -m pytest tests/ -v
docker compose build
docker compose up
```

One file, one job. `loop.py` does loop logic. `budget.py` does budget. `db.py` does storage.

---

## License

MIT
