# Think9 Decision Intelligence — MVP Development Roadmap

**Version:** 1.0
**Status:** Draft for review
**Companion docs:** `decision-intelligence-mvp.md` (MVP scope), `retrieval-system.md` (chunking/embedding/ranking), `ingestion-system.md`, `agentic-workflow.md`, `prompts.md`, `decision-intelligence-spec.md`.

This is the build plan for a **4-week MVP**, assuming **2–3 full-time engineers** (1 backend/RAG, 1 full-stack, 0.5 data). It is deliberately aggressive — Week 1 foundations must not slip or the downstream weeks compress.

---

## 0. Prerequisites & Standing Decisions (do before Week 1)

| Item | Decision (from prior docs) |
|------|----------------------------|
| Taxonomy | 6 primary categories + documented sub-categories (§1 below) |
| Vector DB | **pgvector** (local Docker dev; managed Postgres at staging) |
| Embeddings | `text-embedding-3-small` MVP default; `BGE-M3` profile for privileged content |
| LLMs | `gpt-4o-mini` (router/escalation) + `gpt-4o` (brief/validation/risk) |
| Retrieval | hybrid dense + BM25; weights 0.50/0.25/0.15/0.10; thresholds 0.55/0.35 |
| Backend/UI | FastAPI + Next.js; Celery/Redis for background jobs |
| Repo | monorepo: `api/`, `web/`, `ingest/`, `docs/`, `infra/` |

### 1.0 Think9 decision types (the taxonomy to document in Week 1)

**6 primary categories** (drives routing, brief templates, gate policies, category boost):

| Category | Sub-categories (initial set — ~24) |
|----------|-------------------------------------|
| **procurement** | vendor_renegotiation, moq_negotiation, price_change, contract_terms, vendor_onboarding, vendor_benchmark, vendor_offboarding |
| **brand** | brand_voice, campaign_approval, sponsorship, product_packaging, partnership |
| **product** | launch_timing, formulation_change, sku_retirement, co_pack_selection |
| **hr** | hiring, comp_band, retention, reorg |
| **legal** | contract_review, exclusivity, indemnity, compliance |
| **ops** | supply_disruption, capacity, fulfillment, process_change |

**Decision:** freeze this taxonomy by end of Week 1. Extensions are additive (sub-categories), never renames, after freeze. Each type is documented as: name, category, default approval gates, risk profile, example prompts (for the router few-shot).

---

## 2. Roadmap Overview (4 weeks)

```
        W1              W2              W3              W4
FOUNDATIONS       INGEST+RAG        BRIEFS+UI        SLACK+ANALYTICS
─────────────────┬─────────────────┬─────────────────┬────────────
schema+taxonomy   ingestion mocks   brief generation  Slack bot
vector DB setup   chunking+embed    contradiction     analytics dash
sample dataset    retrieval + API   confidence+esc    perf+optimization
[par: data]       [par: API/UI]     web UI            docs + demo
```

---

## Week 1 — Foundations

### Tasks
- [ ] **Data schema design** — `documents`, `chunks` (+ pgvector), `decisions`, `decision_briefs`, `brief_chunks`, `flags`, `queries`, `outcomes`, `vendors`, `brands` (DDL in MVP doc §7).
- [ ] **Document Think9 decision types** — freeze the §1.0 taxonomy (6 categories, ~24 sub-categories) into `docs/taxonomy.md`; wire it to the router few-shot.
- [ ] **Set up vector DB** — **local** pgvector via Docker Compose (dev). Rationale: free, zero-ops, adequate for 6–20k chunks; revisit at Phase 2 (Qdrant/Weaviate) behind the `VectorStore` interface.
- [ ] **Sample dataset** — 50 synthetic meeting transcripts, 10 playbooks (2 per brand), 30 past decisions with outcomes. Generated from real templates + LLM-assisted mock content; must include deliberate contradictions for Week 3 testing.

### Tech stack
| Layer | Choice |
|-------|--------|
| DB | Postgres 16 + pgvector (Docker image `pgvector/pgvector:pg16`) |
| Migration | Alembic (SQLAlchemy) |
| Backend skeleton | FastAPI + Pydantic v2 |
| Infra | Docker Compose (dev only) |

### Deployment target
- **Dev only.** `docker compose up` must bring up Postgres + API + seed scripts. No cloud deployment this week.
- CI: lint + schema/seed smoke tests on every PR.

### Success metrics (Week 1 exit criteria)
- [ ] Schema migrations apply cleanly; seed job idempotent.
- [ ] Taxonomy doc signed off (categories + sub-categories frozen).
- [ ] Sample dataset fully seeded: **50 transcripts / 10 playbooks / 30 decisions**, each with valid `sha256` and chunk rows.
- [ ] HNSW index query returns correct neighbors on a smoke query.

---

## Week 2 — Ingestion Pipeline + Retrieval

### Tasks
- [ ] **Ingestion pipeline (mock integrations)** — mock adapters for Zoom/Drive/Slack/CRM emitting the same event shapes as production (§2 of ingestion spec); pipeline: validate → persist-raw → parse → normalize → chunk → embed → index.
- [ ] **Chunking + embedding** — per doc_type chunker (§1 retrieval spec), `text-embedding-3-small` batch 64, embedding cache by `sha256`.
- [ ] **Retrieval backend** — hybrid semantic + BM25 (pgvector + TSVECTOR), category boost + freshness weights, `RETRIEVE_OK/WEAK/NONE` thresholds.
- [ ] **REST API** — `POST /v1/queries` (question → categorized → retrieval → grounded answer) + `GET /v1/search` for the UI.

### Tech stack
| Layer | Choice |
|-------|--------|
| Ingestion | Celery workers + Redis (queue); `unstructured` + `python-docx` parsers |
| Storage | Local S3-compatible (LocalStack) or minio for raw vault |
| Embeddings | OpenAI `text-embedding-3-small` (1,536 dim) |
| Retrieval | pgvector HNSW + Postgres FTS (single query) |
| API | FastAPI (`/v1/queries`, `/v1/search`, `/v1/ingest/*`) |

### Deployment target
- **Staging**: managed Postgres (RDS/Aurora) with pgvector; API + workers on Render/Railway or ECS Fargate; secrets in Secret Manager. CI deploys on green.
- Dev keeps Docker Compose; staging is the demo-credible environment.

### Success metrics (Week 2 exit criteria)
- [ ] 90-doc sample dataset ingests in **< 5 min**, idempotent re-run.
- [ ] Gold set (50 Q/A pairs) seeded; **recall@20 ≥ 0.85**, **nDCG@10 ≥ 0.75**.
- [ ] Hybrid ranking beats dense-only and BM25-only on the gold set.
- [ ] `POST /v1/queries` returns categorized, cited answers; **p95 < 1 s**.
- [ ] Evidence-gap path returns cleanly when retrieval is weak (no hallucination).

---

## Week 3 — Decision Briefs + Web UI

### Tasks
- [ ] **Decision brief generation** — Agent 3 prompt (prompts.md §2): recommendation + confidence, exactly 3 precedents, 4-type risk block, alternatives, approval flow; JSON-schema validated server-side.
- [ ] **Contradiction detection** — Agent 4 pass A against `decisions` + `learnings`; severity classification; flags surface on brief.
- [ ] **Confidence scoring + escalation rules** — confidence from evidence density + precedent outcomes + flags; escalation ladder levels 0–2 (agentic spec §6).
- [ ] **Web UI** — query input + brief display (citations, flags, confidence breakdown, precedents side-by-side), basic ingestion status page.

### Tech stack
| Layer | Choice |
|-------|--------|
| LLM | `gpt-4o` (brief/validation/risk), `gpt-4o-mini` (router/escalation); prompts in registry |
| Structured output | Pydantic JSON schema + validation, 1 re-prompt, fail-closed |
| Web | Next.js (React/TS) + Tailwind; API client to `/v1` |
| State | Decision workspace backed by `decision_briefs` + `flags` tables |

### Deployment target
- **Staging promoted to "demo environment"**: full stack live with the 90-doc corpus; UI + API reachable for stakeholder review.
- Brief generation runs as async job (ack + notify) given p95 up to 30 s.

### Success metrics (Week 3 exit criteria)
- [ ] **100% citation validity** (every cited chunk exists in `brief_chunks`); panel rates brief faithfulness **≥ 4/5** on 10 briefs.
- [ ] Exactly-3-precedents format holds; precedents always carry `why/how_applies`.
- [ ] **Contradiction precision ≥ 80%** on the seeded deliberate-contradiction set (Week 1 dataset).
- [ ] Confidence correlates with human ratings (**r ≥ 0.6** on 30 briefs).
- [ ] Escalation ladder fires correctly for seeded high-risk/novel cases.

---

## Week 4 — Slack, Analytics, Optimization, Demo

### Tasks
- [ ] **Slack integration** — Bolt app: `/think9 <question>`, `/think9 brief <question>`; async ack → result reply with brief summary + link; follow-ups in thread reuse `query_id`.
- [ ] **Analytics dashboard** — usage (queries/day, by category), decision outcomes (result mix), cost (per query / per brief by model), retrieval quality (manual rating capture).
- [ ] **Performance testing + optimization** — load test `/v1/queries`; tune `ef_search`, hybrid weights, embedding batch/concurrency; cache repeated questions (TTL 24 h).
- [ ] **Documentation + demo** — README, setup runbook, taxonomy doc, demo script (3 scripted scenarios incl. a contradiction and a novel decision).

### Tech stack
| Layer | Choice |
|-------|--------|
| Slack | `slack-bolt` (Python), Events API + slash commands |
| Analytics | Reuse `queries`/`outcomes` tables + lightweight dashboard views; no new DB |
| Perf | k6/Locust load script; pgvector `ef_search` tuning; p95 dashboards |
| Docs | `docs/README.md` index + runbooks (ingestion-system §7 style) |

### Deployment target
- **Production-like demo environment** (staging with prod-equivalent settings); Slack app connected to a test workspace.
- Optional: single-instance production behind it if sign-off is immediate.

### Success metrics (Week 4 exit criteria)
- [ ] Slack: brief from mention to reply **p95 < 30 s**; 10/10 demo questions answered without errors.
- [ ] Analytics dashboards live: usage, outcomes, **cost per query < $0.10**.
- [ ] Load: **50 concurrent queries** with p95 < 2 s, zero failures; no p95 regression after tuning.
- [ ] Demo passes: 3 scripted scenarios; docs + runbook complete; stakeholders can self-serve a query.

---

## 3. Cross-cutting Requirements

| Concern | Where it lands |
|---------|----------------|
| Security | W1 schema (ACL fields); W2 redaction pass; W3 fail-closed validation; secrets never in code |
| Observability | W2 trace_id on queries; W3 agent events; W4 analytics + cost dashboard |
| Evaluation | W2 gold set + nDCG; W3 panel brief ratings; W4 load + regression gate |
| Backward compat | `VectorStore`/`Embedder`/`LLMProvider` interfaces from spec §14 from W1 — no rewrite later |

## 4. Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Week 1 slips (schema/taxonomy) | Freeze date for taxonomy; sample dataset generated in parallel |
| Embedding/LLM cost overrun in demo | Per-query budget caps; question cache; batch embedding |
| Brief hallucination risk | Citation validity enforced in W3 (100% bar); evidence-gap mode default on weak retrieval |
| 4-week scope creep | Non-features (MVP doc §4) are hard-excluded; anything new goes to Phase 2 backlog |
| Demo data too clean → no contradiction shown | Seeded deliberate contradictions (W1) used in demo scenario 2 |

## 5. Definition of Done (overall MVP)
- The 90-doc corpus is live; `/think9 brief` returns a cited, flagged, confidence-scored brief; Slack + web both work; contradiction and evidence-gap paths demonstrable; analytics show usage + cost; all 4 week-exit metrics green.
