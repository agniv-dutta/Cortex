# Think9 Backend (MVP)

Python 3.12 + FastAPI decision-intelligence backend. Implements the architecture in `../docs/`:

- **Hybrid retrieval** — pgvector HNSW (dense) + Postgres FTS (sparse), weighted `0.50/0.25/0.15/0.10` (semantic/BM25/category/freshness) with evidence thresholds.
- **Agent pipeline** — A1 Router → A2 Retriever → A3 Synthesizer → A4 Validator, orchestrated by a deterministic DAG (`app/services/orchestrator.py`) with a bounded revision loop and escalation ladder.
- **LLM tiering** — cheap tier (routing/classification) vs premium tier (brief synthesis/validation) behind `LLMProvider`.
- **Provider interfaces** — `Embedder`, `LLMProvider`, `VectorStore` are swap-in by config (see `app/providers/`).

## Layout

```
app/
├── core/          # settings, db engine, ulid, envelope
├── db/models/     # SQLAlchemy models (MVP schema, spec §7)
├── schemas/       # Pydantic contracts (envelope, brief, validation)
├── providers/     # Embedder / LLM / VectorStore interfaces + impls
├── prompts/       # versioned prompt templates (prompts.md)
├── services/      # A1-A4 agents + orchestrator + escalation
├── ingest/        # chunker, parsers, ingestion pipeline
├── api/v1/        # REST endpoints
└── workers/       # Celery app + async tasks
```

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; use source .venv/bin/activate on Unix
pip install -e ".[dev]"

cp .env.example .env              # set OPENAI_API_KEY / ANTHROPIC_API_KEY
docker compose up -d              # Postgres 16 + pgvector, Redis
python scripts/init_db.py         # create tables + HNSW index (dev bootstrap)
python scripts/seed_sample_data.py  # seed 90-doc sample corpus
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

## Key endpoints (`/v1`)

| Endpoint | Purpose |
|----------|---------|
| `POST /queries` | Ask a question → categorized, grounded answer (cheap tier) |
| `POST /decisions` | Create a decision → generate decision brief (premium tier) |
| `GET /decisions/{id}` | Fetch decision + brief + flags |
| `PUT /decisions/{id}/outcome` | Record outcome (learning loop) |
| `GET /search?q=` | Corpus search (dashboard) |
| `POST /ingest/{source}` | Trigger ingestion for a source ref |
| `GET /healthz` | Liveness/readiness |

## Tests

```bash
pytest                                   # unit + smoke tests
python scripts/seed_sample_data.py --fake-embeddings   # run without API keys
```

## Config (`.env`)

All knobs from `app/core/config.py` — model tiers, hybrid weights, thresholds, budgets. See `retrieval-system.md` §3 for tuning guidance.
