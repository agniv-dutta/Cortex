# Think9 Decision Intelligence

Centralized AI-powered decision intelligence for Think9. Ingests meetings, playbooks, decisions, contracts, and post-mortems; retrieves institutional knowledge; generates grounded decision briefs with precedents, risks, contradiction flags, and approval flows; tracks outcomes for continuous learning.

## Repository layout

```
Cortex/
├── backend/            # Python/FastAPI backend (MVP)
│   └── README.md       # backend setup + run instructions
├── docs/               # design specifications
│   ├── decision-intelligence-spec.md    # full target architecture
│   ├── decision-intelligence-mvp.md     # MVP scope (features, sources, UX, schema)
│   ├── agentic-workflow.md              # multi-agent orchestration
│   ├── ingestion-system.md              # automated ingestion + adapters
│   ├── retrieval-system.md              # chunking, embeddings, ranking, vector DB
│   ├── prompts.md                       # prompt specs + few-shot + settings
│   ├── expert-agents.md                 # specialized expert panel + meta-agent
│   ├── roadmap-mvp.md                   # 4-week build plan + success metrics
│   └── cost-performance-analysis.md     # LLM/vector-DB economics + ROI
└── README.md           # this file
```

## Design at a glance

- **Retrieval:** hybrid dense (pgvector HNSW) + sparse (Postgres FTS), weighted `0.50 semantic / 0.25 BM25 / 0.15 category / 0.10 freshness`, cross-encoder re-rank, evidence thresholds (0.55/0.35).
- **Agents:** A1 Query Router → A2 Context Retriever → A3 Decision Synthesizer → A4 Validation, coordinated by a deterministic DAG with a bounded revision loop and escalation ladder.
- **LLM tiering:** cheap model (`gpt-4o-mini`) for routing/classification; premium (Claude Sonnet 4) for brief synthesis + validation.
- **Posture:** provider-agnostic — `Embedder`, `LLMProvider`, `VectorStore` interfaces keep every vendor swappable by config.

## Quickstart (backend)

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
cp .env.example .env                            # add API keys
# start Postgres + Redis (Docker)
docker compose up -d
python scripts/init_db.py                       # create tables (dev bootstrap)
python scripts/seed_sample_data.py              # seed 90-doc sample corpus
uvicorn app.main:app --reload
```

See `backend/README.md` for full instructions, endpoint list, and test commands.

## Documents

Design specs live in `docs/` (see table above). Every backend module references the relevant section so code and spec stay traceable.
