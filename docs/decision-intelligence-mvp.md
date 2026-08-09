# Think9 Decision Intelligence — MVP Definition

**Version:** 1.0
**Status:** Draft for review
**Scope:** Minimum Viable Product — Phase 1
**Companion doc:** `docs/decision-intelligence-spec.md` (full target architecture). This doc is the scoped, buildable slice.

---

## 1. Core Features (ranked by impact)

Ranking reflects business impact first; the build order (right column) differs because some features are prerequisites for others.

| # | Feature | Impact | Effort | Build order | Why it matters |
|---|---------|--------|--------|-------------|----------------|
| 1 | **Semantic search across institutional knowledge** | ★★★★★ | Medium | 2 | The base capability; every other feature consumes it. Turns 2+ years of meetings, playbooks, and decisions into a findable corpus. |
| 2 | **Auto-categorize incoming queries** (procurement, brand strategy, product, HR, legal) | ★★★☆ | Low | 1 | Cheap, immediately useful, and *required* by retrieval routing, brief templates, and alert rules. Ship first as a dependency. |
| 3 | **Generate decision briefs with 2–3 historical precedents** | ★★★★★ | High | 3 | The flagship output. Converts retrieval into a citable, actionable artifact. |
| 4 | **Confidence scoring on recommendations** | ★★★★ | Medium | 4 | Trust signal. Lets users know when to lean on the brief vs. dig deeper. Depends on retrieval quality, so it lands last. |

### Success criteria (MVP exit)
- Semantic search returns relevant results for ≥80% of a 50-question gold set (top-5 contains the intended doc).
- Query categorization accuracy ≥ 90% on a labeled set of 100 queries.
- Briefs always cite 2–3 real precedents with valid chunk references (no hallucinated citations).
- Confidence score correlates with human ratings (r ≥ 0.6 on 30 reviewed briefs).

---

## 2. Phase 1 Data Sources

Three sources. Volume model is trivially small for modern stacks — the constraints are format normalization and PII handling, not scale.

| Source | Volume (assumed) | Shape | Format | MVP handling |
|--------|------------------|-------|--------|--------------|
| **Meeting transcripts** | 50+ / month (~10k tokens each) | Speaker-tagged dialog + generated minutes | STT export (VTT/SRT/plain text), minutes as DOCX/MD | Uploaded via dashboard or S3 drop; speaker turns preserved; PII scrub for names of external parties (internal names kept for attribution) |
| **Brand playbooks** | 3–5 docs per brand (assume ~20–25 total) | Rules, voice/tone, constraints, launch cadence | DOCX/PDF/MD | Versioned on upload; each version = one document; rule-aware chunking |
| **Decision log** | 100+ historical decisions | Statement, rationale, decision class, outcome (where known), date | CSV/JSON export + narrative MD | Migration batch in; each row becomes a `decisions` document; outcomes attached when present |

### Derived corpus size estimate
- Meeting chunks: ~1.2M–1.5M tokens → ~4–5k chunks (at ~300 tokens/chunk)
- Playbook chunks: ~150–250 chunks
- Decision chunks: ~100–200 chunks (kept whole, self-contained)
- **Total: ~5–6k chunks, ~2M tokens** — fits comfortably on a single Postgres+pgvector instance; embed cost ≈ pennies per full re-embed.

### Out of scope for Phase 1 ingestion
- Audio/raw video parsing (transcripts must already exist) — listed under non-features.
- Contracts, post-mortems, negotiation templates — Phase 2 (schema already supports them).

---

## 3. User Workflows

### 3.1 Slack — quick queries (primary daily touchpoint)
```
User:   /think9 should we renegotiate the Acme deal before Q4?
Slack:  🤔 Categorizing… [procurement]
        🧠 Brief (72% confidence)
        • RECOMMENDATION: Renegotiate now — 2 of 3 comparable renewals
          landed better terms when started 2+ quarters out.
        • PRECEDENTS: [1] Acme 2024 renewal (outcome: +6% discount,
          extended lock-in). [2] Northwind 2023 (outcome: walked away,
          better offer). [3] <playbook> vendor negotiation rule §4.
        • RISKS: Lock-in clause (high) — contradicts playbook §7.
        • APPROVAL: Legal → Procurement (estimated 24h).
        [Open in dashboard] [Ask follow-up]
```
- Bot commands: `/think9 <question>`, `/think9 brief <question>`, `/think9 search <term>`.
- Follow-up threading: same thread, same context session.
- Response SLA: < 10s for search, < 30s for briefs (async ack + result reply).

### 3.2 Web dashboard — deep-dive exploration
- **Search & browse:** full-text + semantic search across all sources; facet by source, brand, date, category; click-through to raw document + highlighted chunk.
- **Decision workspace:** draft decision → generate brief → review precedents (side-by-side with source chunk) → adjust → record outcome later.
- **Confidence inspection:** why the score is what it is (evidence thickness, contradiction flags).
- **Admin:** upload sources, view ingestion status, approve learnings.

### 3.3 Email alerts — contradiction detection
- Background job (nightly) scans **new/in-flight decisions** against the `learnings` + `decisions` collections.
- On flag: email to requester + owning team lead.
```
Subject: ⚠️ Contradiction: decision dec_01JZ… conflicts with past learning
Body:    Decision "Renegotiate Acme before Q4" contradicts:
         - Acme 2024 post-mortem (what went wrong, citation link)
         - Brand playbook §7 (lock-in rule)
         Action: review in dashboard | override with rationale | request changes
```
- MVP volume: only decisions in `draft`/`pending_review` status are scanned; no spamming of approved items.

---

## 4. Non-Features (explicitly out of MVP scope)

| Excluded | Rationale | Revisit when |
|----------|-----------|--------------|
| Real-time video/audio ingestion | Requires STT pipeline + streaming infra; transcripts arrive already transcribed in Phase 1 | When live call transcription is a confirmed requirement (Phase 3+) |
| Autonomous decision execution | Trust and compliance risk; humans approve everything. System recommends and gates only. | After contradiction precision ≥ 90% and audit chain in production |
| Cross-portfolio P&L optimization | Needs finance data warehouse integration, ML forecasting — heavy, orthogonal | Phase 4+, only if a concrete business case emerges |
| (bonus) Vendor contracts / post-mortem ingestion | Rich but heavier to handle safely (legal redaction, sensitive PII) | Phase 2 |

---

## 5. Tech Stack (MVP — pragmatic, single-service)

Keeps the BYO philosophy from the full spec but defaults to boring, low-ops choices.

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | **Python 3.12 + FastAPI** | Fast iteration, strong LLM/embedding ecosystem |
| Orchestration | **Celery + Redis** (optional) | Background jobs: ingest, brief generation, alert scans. Can start as `BackgroundTasks` if volume is tiny |
| Database | **PostgreSQL 16 + pgvector** | One operational DB for relational + vectors; no separate vector store in MVP |
| Vector search | **pgvector** HNSW, cosine | Corpus is ~6k chunks; no need for a distributed vector DB yet |
| Full-text | **Postgres FTS (TSVECTOR)** | Hybrid dense+sparse in the same query; no extra index service |
| Embeddings | **OpenAI `text-embedding-3-small`** (1,536 dim) default; `BGE-M3` self-hosted as a fallback profile | Cheap, fast, good quality; swap is a config change behind `Embedder` interface |
| LLM | **`gpt-4o-mini`** for categorization; **`gpt-4o`** (or Claude Sonnet 4) for brief generation | Categorization is cheap/structured; briefs need stronger reasoning + instruction following |
| Reranker | **Skip in MVP** — hybrid score + threshold | Rerankers add cost/complexity; revisit when corpus grows or nDCG slips |
| Object storage | **S3** (raw vault) | Immutable raw copies for audit + re-processing |
| Slack | **Bolt for Python** (`slack-bolt`) | Socket mode in dev; HTTP events in prod |
| Dashboard | **Next.js (React + TS)** | Fast to build, great data-table/editor ecosystem |
| Alerts | **SES or SendGrid** email + Slack DM fallback | Simple, reliable |
| Infra | **Docker Compose (dev)** → ECS/GKE or Render/Railway (prod) | No Kubernetes in MVP |
| Secrets | **AWS Secrets Manager / Vercel env / .env (dev)** | Keep secrets out of code |

### Interface boundaries preserved from full spec
Only 5 interfaces matter for MVP: `Embedder`, `LLMProvider`, `VectorStore` (pgvector impl), `ObjectStore` (S3 impl), `SlackNotifier`/`EmailNotifier`. Everything else is internal.

---

## 6. System Diagram (MVP)

```
 Slac k  ─┐
 Dashboard┼──► FastAPI ──┬─► CategoryClassifier ──► QueryRouter
 Email   ─┘              │        │ (pgvector/LLM)
                         ├─► Retriever (hybrid: pgvector + FTS)
                         ├─► BriefGenerator (LLM + context pack)
                         ├─► ContradictionScanner (nightly job)
                         ├─► IngestWorker (parse→chunk→embed→insert)
                         └─► Notifiers (Slack/Email)
                                │
        ┌───────────────────────┼──────────────────────────┐
        ▼                       ▼                          ▼
 PostgreSQL 16 + pgvector   S3 (raw vault)         LLM/Embed providers
 documents/chunks/decisions                        (OpenAI | BGE-M3)
 briefs/flags/queries
```

---

## 7. Database Schema (PostgreSQL 16 + pgvector)

```sql
-- extensions
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------- source documents ----------
CREATE TABLE documents (
  id            text PRIMARY KEY,               -- ULID: doc_01JZ…
  doc_type      text NOT NULL CHECK (doc_type IN
                ('meeting','playbook','decision','guideline')),
  source        text NOT NULL,                  -- e.g. 'slack_upload','s3','csv'
  title         text NOT NULL,
  version       text NOT NULL DEFAULT '1',
  sha256        text NOT NULL,
  status        text NOT NULL DEFAULT 'active'  -- active|superseded|archived
                CHECK (status IN ('active','superseded','archived')),
  category      text,                           -- procurement|brand|product|hr|legal
  brands        text[] DEFAULT '{}',            -- ['cortex','nova']
  metadata      jsonb NOT NULL DEFAULT '{}',    -- meeting_id, brand, author, …
  raw_ref       text NOT NULL,                  -- s3://raw/…
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (sha256, version)
);

-- ---------- chunks (vector index payload) ----------
CREATE TABLE chunks (
  id           text PRIMARY KEY,                -- chunk_<hash>
  document_id  text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index  int NOT NULL,
  content      text NOT NULL,
  role         text NOT NULL DEFAULT 'body'     -- body|title|heading|clause|…
  section_path text[] DEFAULT '{}',
  tokens       int NOT NULL,
  embedding    vector(1536) NOT NULL,           -- dims match embedder
  UNIQUE (document_id, chunk_index)
);
CREATE INDEX idx_chunks_embedding ON chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 32, ef_construction = 200);
CREATE INDEX idx_chunks_fts ON chunks
  USING gin (to_tsvector('english', content));

-- ---------- historical decisions ----------
CREATE TABLE decisions (
  id           text PRIMARY KEY,                -- dec_…
  statement    text NOT NULL,
  category     text NOT NULL,                   -- drives class-specific briefs
  decision_class text NOT NULL,                 -- procurement|brand|product|hr|legal|ops
  rationale    text,
  outcome      text,                            -- success|partial|failure|unknown
  outcome_notes text,
  decided_at   date,
  brands       text[] DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- ---------- user queries + categorization ----------
CREATE TABLE queries (
  id            text PRIMARY KEY,               -- qry_…
  user_id       text,
  channel       text NOT NULL,                  -- slack|web|api
  question      text NOT NULL,
  category      text,
  category_confidence float,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ---------- generated decision briefs ----------
CREATE TABLE decision_briefs (
  id            text PRIMARY KEY,               -- brf_…
  decision_id   text REFERENCES decisions(id),  -- null if ad-hoc question
  query_id      text REFERENCES queries(id),
  brief         jsonb NOT NULL,                 -- recommended_action, precedents,
                                                -- risk_factors, approval_flow
  confidence    float NOT NULL,
  model_info    jsonb NOT NULL,                 -- prompt_versions, embedder, model
  status        text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft','pending_review','in_approval',
                                  'approved','rejected','executed','archived')),
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ---------- brief → chunk provenance (grounding) ----------
CREATE TABLE brief_chunks (
  brief_id  text NOT NULL REFERENCES decision_briefs(id) ON DELETE CASCADE,
  chunk_id  text NOT NULL REFERENCES chunks(id),
  relevance float NOT NULL,
  PRIMARY KEY (brief_id, chunk_id)
);

-- ---------- contradiction flags ----------
CREATE TABLE flags (
  id            text PRIMARY KEY,               -- flg_…
  brief_id      text NOT NULL REFERENCES decision_briefs(id) ON DELETE CASCADE,
  flag_type     text NOT NULL CHECK (flag_type IN
                ('contradicts','supersedes','repeats_failure','no_precedent')),
  severity      text NOT NULL CHECK (severity IN ('low','medium','high')),
  cited_chunk   text REFERENCES chunks(id),
  conflict_text text NOT NULL,
  resolution    text,                           -- accept|override|rejected|ignored
  resolution_by text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ---------- outcome tracking (Phase 1: manual entry) ----------
CREATE TABLE outcomes (
  decision_id   text PRIMARY KEY REFERENCES decisions(id),
  result        text NOT NULL CHECK (result IN ('success','partial','failure','superseded')),
  metric_deltas jsonb DEFAULT '{}',             -- {'mrr_delta_pct': 6, 'note': '…'}
  narrative     text,
  recorded_by   text,
  recorded_at   timestamptz NOT NULL DEFAULT now()
);

-- ---------- alert log ----------
CREATE TABLE alerts (
  id         text PRIMARY KEY,
  brief_id   text REFERENCES decision_briefs(id),
  kind       text NOT NULL,                     -- contradiction|weak_evidence|gate
  channel    text NOT NULL,                     -- email|slack
  recipients text[] NOT NULL,
  sent_at    timestamptz NOT NULL DEFAULT now()
);
```

### Indexing notes
- `chunks.embedding` uses HNSW cosine; re-run `ANALYZE` after bulk loads.
- `chunks` FTS index supports hybrid query; hybrid weight: `0.6 * cosine + 0.4 * ts_rank` (tuned in eval).
- Queries/briefs tables are append-heavy; archive after 90 days if needed.

---

## 8. API Contracts

All `/v1` endpoints, JSON. Auth: Bearer token (Slack handles its own signing; dashboard users via session).

### 8.1 `POST /v1/queries` — ask a question
```jsonc
// Request
{ "question": "Should we renegotiate the Acme deal before Q4?",
  "channel": "slack", "user_id": "U123" }

// Response — categorized + answer-or-brief
{
  "query_id": "qry_01JZ8X…",
  "category": "procurement",
  "category_confidence": 0.94,
  "answer": "…grounded answer with inline citations…",   // search mode
  "mode": "answer",                                       // or "brief"
  "citations": [{ "document_id": "doc_…", "chunk_id": "chunk_…", "title": "…" }]
}
```

### 8.2 `POST /v1/decisions` — generate a decision brief (flag feature)
```jsonc
// Request
{ "statement": "Renegotiate Acme enterprise renewal before Q4",
  "category": "procurement", "brands": ["cortex"],
  "context_notes": "counterparty signaled 8% hike" }

// 201 Created
{
  "brief_id": "brf_01JZ8…",
  "confidence": 0.72,
  "recommended_action": {
    "action": "Start renegotiation now…",
    "rationale": "2 of 3 comparable renewals improved terms with earlier starts",
    "alternatives": [{ "action": "Wait until Q4", "tradeoff": "accepts 8% hike risk" }]
  },
  "precedents": [
    { "decision_id": "dec_01…", "outcome": "success",
      "relevance": 0.88, "summary": "Acme 2024 renewal gained +6% discount" },
    { "decision_id": "dec_02…", "outcome": "failure", "relevance": 0.81,
      "summary": "Northwind walk-away produced a better counteroffer" },
    { "document_id": "doc_…", "chunk_id": "chunk_…",
      "relevance": 0.79, "summary": "Playbook §4: negotiation timing rule" }
  ],
  "risk_factors": [
    { "risk": "Lock-in clause triggers on renegotiation",
      "severity": "high", "likelihood": "medium",
      "source_chunk": "chunk_…" }
  ],
  "approval_flow": { "gates": ["legal", "procurement"], "sla_hours": 24 },
  "flags": [
    { "flag_type": "contradicts", "severity": "high",
      "cited_chunk": "chunk_…",
      "conflict_text": "Post-mortem: early renegotiation caused $120k penalty in 2024" }
  ],
  "provenance": ["chunk_…","chunk_…"],
  "model_info": { "embedder": "text-embedding-3-small@1",
                  "llm": "gpt-4o", "prompt_version": "brief_v3" }
}
```

### 8.3 `GET /v1/decisions/{id}` — fetch decision + brief + flags
```jsonc
{ "decision_id": "dec_…", "statement": "…", "status": "pending_review",
  "briefs": [ /* latest brief first */ ], "flags": [ /* active flags */ ] }
```

### 8.4 `PUT /v1/decisions/{id}/outcome` — record outcome
```jsonc
// Request
{ "result": "success", "metric_deltas": { "discount_pct": 6 },
  "narrative": "Early start secured better terms", "recorded_by": "U123" }
// Response 200 { "decision_id": "…", "outcome_recorded": true }
```

### 8.5 `POST /v1/ingest` — trigger source ingestion
```jsonc
{ "source": "s3", "key": "transcripts/2026-08/monthly.zip" }
// 202 { "job_id": "ing_…", "status": "queued" }
```

### 8.6 `GET /v1/search?q=&filters=` — dashboard search
```jsonc
// Response
{ "results": [ { "chunk_id": "…", "document_id": "…", "title": "…",
  "snippet": "…", "score": 0.87, "source": "meeting", "date": "2026-07-12" } ],
  "total": 14 }
```

### 8.7 Slack event handler — `POST /slack/events` (Bolt)
- Handles `app_mention`, `slash_command`, `message` in DM; verifies Slack signatures.
- Follow-ups in a thread reuse `query_id` for context continuity.

### 8.8 Alerts (outbound, no client call)
- **Email:** nightly contradiction scan → `alerts` table row + SES/SendGrid send.
- **Slack DM:** optional immediate flag on brief generation (config flag).

---

## 9. Deployment & Environments (MVP)

- **Dev:** `docker compose up` — Postgres+pgvector, Redis, API, worker, Next.js, mock LLM profile for tests.
- **Prod:** API + worker on one container image (entrypoint split), Postgres RDS, S3, secrets in Secret Manager. Horizontal scale = +worker replicas.
- **CI:** lint → unit tests (schema, chunker, classifier) → integration test against pgvector test DB → eval gate (nDCG/regression from §1) on any retrieval/embedding change.

---

## 10. MVP Phase Plan

| Step | Deliverable | Duration |
|------|-------------|----------|
| M1 | Schema + ingest for 3 sources; `documents`/`chunks` seeded | 1 wk |
| M2 | Semantic search API + hybrid retrieval + eval gold set v1 | 2 wks |
| M3 | Categorizer (LLM + few-shot, fallback rules) | 1 wk |
| M4 | Brief generator (precedents, risks, approval flow, citations) | 2 wks |
| M5 | Confidence scoring + thresholds | 1 wk |
| M6 | Slack bot + dashboard | 2 wks |
| M7 | Contradiction scanner + email alerts | 1 wk |
| M8 | Outcome entry + learnings loop (feed outcome back into decisions) | 1 wk |
| **Total** | | **~11 wks** |

---

## 11. MVP Risks

| Risk | Mitigation |
|------|------------|
| Transcript quality (STT errors) pollutes retrieval | Store raw + clean; allow document-level ignore; measure retrieval quality per source |
| Hallucinated precedents | Citation must resolve to real `brief_chunks` rows or the brief is rejected (§8.2 `provenance`); gold-set check in CI |
| Categorizer bias on new question shapes | Log every categorization; weekly human audit of mislabeled samples; few-shot examples grown from data |
| pgvector outgrows single node | Not in Phase 1 (6k chunks); interface isolates swap to dedicated vector DB |
| Slack latency on briefs | Async ack + result reply; brief cache keyed by question hash (TTL 24h) |

---

*Theories of change: this doc scopes Phase 1 only. The full target architecture in `decision-intelligence-spec.md` remains the north star; no Phase-1 decision should preclude the BYO interfaces listed in §5.*
