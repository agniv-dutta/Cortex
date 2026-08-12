# Think9 Decision Intelligence System — Technical Specification

**Version:** 1.0
**Status:** Draft for review
**Owner:** Decision Intelligence WG
**Date:** 2026-08-09
**Stack posture:** Vendor-agnostic / bring-your-own (BYO). All infrastructure services behind pluggable interfaces with reference implementations.

---

## 1. Executive Summary

Think9 will deploy a centralized AI decision-intelligence system that turns the company's unstructured operational corpus — meeting transcripts, minutes, brand playbooks, vendor contracts, launch post-mortems, and historical decisions — into a queryable, auditable decision-support layer.

**Core value:** every new operational decision is produced as a *decision brief* grounded in company memory: a recommended action, the historical precedents it leans on, the risks it carries, the approval flow it must pass, and an automatic alert when the proposal contradicts past learnings.

**Outcome loop:** each decision is tracked through approval → execution → outcome, and the outcome is fed back into the corpus so the system's reasoning measurably improves over time.

### 1.1 Goals
- G1. Ingest and index all listed unstructured sources into a vector store with full provenance and ACL fidelity.
- G2. Answer operational questions with retrieved, ranked, citable context.
- G3. Generate decision briefs containing: recommended action, historical precedents, risk factors, approval flow.
- G4. Detect and flag contradictions between proposed decisions and indexed historical learnings.
- G5. Capture decision outcomes and use them to continuously improve retrieval and generation quality.

### 1.2 Non-goals (v1)
- No automated decision *execution* — the system recommends, humans approve.
- No real-time conversational chat UX beyond the decision workflow (v1 is API + thin client).
- No on-prem deployment requirements; must run in any of the major clouds via the BYO layer.
- No support for binary/exotic formats (video-only sources must have audio/transcript first).

### 1.3 Design principles
- **Pluggability:** every provider boundary (vector DB, embedding model, reranker, LLM, object storage, queue) is an interface; swapping requires config change, not code change.
- **Traceability:** every token of generated output can be traced to indexed source chunks (cite-before-you-decide).
- **Human-in-the-loop:** approval gates are mandatory and role-enforced; the system never self-approves.
- **Separation of concerns:** ingestion, retrieval, generation, governance, and learning are independently deployable and independently testable.
- **Security-first:** document-level ACLs, redaction-at-ingest, and a full audit log are non-negotiable.

---

## 2. System Architecture

### 2.1 Context diagram

```
                    ┌─────────────────────────────────────────────────────┐
                    │                    THINK9 USERS                       │
                    │  Operators │ Finance │ Legal │ Brand │ Execs │ Auditors │
                    └──────┬───────────────────────┬───────────────────────┘
                           │                       │
                     Ask question /         Decision briefs,
                     create decision        approvals, alerts
                           ▼                       ▲
                ┌─────────────────────────────────────────────────┐
                │          DECISION INTELLIGENCE PLATFORM           │
                │                                                    │
                │   ┌──────────┐  ┌───────────┐  ┌──────────────┐   │
                │   │ INGEST   │  │ RETRIEVAL │  │ ORCHESTRATOR│   │
                │   └──────────┘  └───────────┘  └──────────────┘   │
                │   ┌──────────┐  ┌───────────┐  ┌──────────────┐   │
                │   │ VECTOR   │  │ LLM       │  │ APPROVAL     │   │
                │   │ STORE    │  │ LAYERS    │  │ GATEWAYS     │   │
                │   └──────────┘  └───────────┘  └──────────────┘   │
                │   ┌──────────┐  ┌──────────────────────────────┐   │
                │   │ OUTCOME  │  │ GOVERNANCE / AUDIT / EVAL    │   │
                │   │ LOOP     │  └──────────────────────────────┘   │
                └─────────────────────────────────────────────────────┘
                          ▲              ▲              ▲
             S3/GCS/Blob  │  Event bus   │  IdP/SSO    │  Notification
                          ▼              ▼              ▼
            Raw documents   Change events   RBAC         Slack/Email/Teams
```

### 2.2 Logical architecture (data flow)

```
SOURCES
 ┌─────────────┬───────────────┬──────────────┬──────────────┬──────────────┐
 │ Exec notes  │  Brand        │ Historical   │ Vendor       │ Launch post- │
 │ (audio txn  │  playbooks    │ decisions +  │ contracts +  │ mortems      │
 │  + minutes) │               │ outcomes     │ negotiation  │              │
 └──────┬──────┴───────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
        │              │              │              │              │
        ▼              ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. INGESTION PIPELINE (per-source adapters, fan-in to common doc model)      │
│    raw storage → parse → normalize → chunk → embed → index → version        │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐   ┌────────────────────────────────────────────┐
│ VECTOR STORE (dense index)   │   │ SEARCH INDEX (sparse/BM25 + metadata)      │
│ collections: docs, chunks,   │   │ per-source corpus; filters: ACL, date,     │
│ decisions, learnings         │   │ type, status                               │
└──────────────┬──────────────┘   └──────────────────┬─────────────────────────┘
               │                                     │
               ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. RETRIEVAL & RANKING                                                        │
│    query understanding → candidate fetch (hybrid) → rerank → context pack     │
└─────────────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. LLM PROMPTING LAYERS                                                       │
│    L0 system → L1 orchestrator → L2 retrieval synthesizer →                  │
│    L3 decision brief generator → L4 contradiction flagger → L5 formatter     │
└─────────────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. APPROVAL GATEWAY                                                            │
│    classify decision → route gate policy → collect approvals → release       │
└─────────────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. OUTCOME LOOP                                                                │
│    execution → outcome intake → KPI attribution → learning doc → reindex     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Component catalog

| ID | Component | Responsibility | Interface |
|----|-----------|----------------|-----------|
| C01 | Ingest orchestrator | Drives per-source pipelines, retries, idempotency | `IngestAdapter`, `Normalizer` |
| C02 | Document parser | PDF/DOCX/audio-transcript/markdown → normalized text + metadata | `Parser` |
| C03 | Chunker | Content-aware chunking per source type | `Chunker` |
| C04 | Embedder | Text → vector via pluggable model | `Embedder` |
| C05 | Vector store | Dense + hybrid search, metadata filtering, snapshots | `VectorStore` |
| C06 | Search index | BM25/sparse + facet filters | `SparseIndex` |
| C07 | Retriever | Multi-strategy candidate fetch + merge | `Retriever` |
| C08 | Reranker | Cross-encoder style scoring of candidates | `Reranker` |
| C09 | LLM gateway | Model routing, prompt versioning, structured output, retries, cost control | `LLMProvider` |
| C10 | Decision orchestrator | Intent, context assembly, brief generation state machine | internal |
| C11 | Contradiction engine | Detects conflicts vs indexed learnings | internal (uses C09, C05) |
| C12 | Approval gateway | Gate policy resolution, approval workflows, escalations | `GatePolicyStore` |
| C13 | Outcome tracker | Outcome intake, KPI mapping, learning doc generation | `OutcomeStore` |
| C14 | Audit/event bus | Provenance, decision events, audit trail | `EventBus` |
| C15 | Eval harness | Offline + online RAG evaluation, drift monitoring | internal |
| C16 | Admin client / API | User-facing API + thin webhook/console | REST + webhooks |

---

## 3. Data Ingestion Pipeline

### 3.1 Source catalog and adapters

| Source | Adapter | Original format | Normalized type | Cardinality trigger | Notes |
|--------|---------|-----------------|-----------------|---------------------|-------|
| Executive meeting audio | `AudioTranscriptAdapter` | MP3/WAV/M4A + STT output | `meeting` | Webhook from STT vendor | STT happens upstream; adapter consumes transcripts + speaker map |
| Executive minutes | `MinutesAdapter` | DOCX/PDF/MD/email | `meeting_minutes` | Upload / mailbox poll | Merged with transcript by meeting_id |
| Brand playbooks | `PlaybookAdapter` | DOCX/PDF/HTML | `playbook` | Git push / upload | Versioned; each version is a document |
| Operational guidelines | `GuidelineAdapter` | DOCX/MD/Notion export | `guideline` | Scheduled export | |
| Historical decisions | `DecisionAdapter` | Structured CSV/JSON from past system + narrative docs | `decision` | Migration batch + daily deltas | Each row carries outcome if known |
| Vendor contracts | `ContractAdapter` | PDF (extracted text) | `contract` | DMS webhook | Legal requires read-only, redaction pass |
| Negotiation templates | `TemplateAdapter` | DOCX/XLSX | `template` | Upload | |
| Launch post-mortems | `PostmortemAdapter` | DOCX/MD/slides | `postmortem` | On launch closeout | Mapped to launch_id |

### 3.2 Pipeline stages (applies to every adapter)

```
raw → validate → persist-raw → parse → extract-metadata → redact/PII →
normalize → resolve-entities → chunk → embed → index → publish-event → done
       └───────────── incremental updates flow through same path ────────────┘
```

1. **Validate** — schema/format check; reject with DLQ error record.
2. **Persist raw** — immutable copy in object storage under `raw/<source>/<sha256>/`. Content-addressed; enables re-processing and audits.
3. **Parse** — extract text + structure via `Parser` per format.
4. **Extract metadata** — source, author, timestamp, meeting_id/launch_id/counterparty, doc version, classification label, owning team.
5. **Redact/PII** — regex + NER-based redaction (contract IDs, personal emails, legal counsel names unless needed). Redaction is *field-level replacement* with a placeholder token; original stays in raw vault only.
6. **Normalize** — map to the canonical Document Model (§4.1). Deduplicate by content hash.
7. **Resolve entities** — link mentions to canonical entities (vendor, brand, product, region) so filters are consistent.
8. **Chunk** — §4.2 strategy.
9. **Embed** — §5.
10. **Index** — write vector + sparse + metadata; atomic via document-level transaction.
11. **Publish event** — `document.indexed` on the event bus (triggers downstream caches and eval sampling).

### 3.3 Orchestration & reliability
- **Orchestrator:** DAG runner (e.g., Step Functions / Cloud Workflows / Airflow / Prefect). Each source adapter is one DAG; failures are retried with exponential backoff and land in a DLQ.
- **Idempotency:** every stage keyed by `(source, sha256, version)`. Re-running a stage is a no-op.
- **Exactly-once index writes:** vector store upserts are idempotent by chunk ID.
- **Incremental sync:** source adapters emit change events; the pipeline only reprocesses changed docs. Playbooks/guidelines use content-hash diffing.
- **Scheduling:** new-doc events are near-real-time; archive re-scans nightly; full re-embed only on model change (versioned embeddings, §5.4).
- **Backfill:** CLI/admin trigger for full re-index; runs in shards with checkpointing.

### 3.4 Provenance & lineage
- Every chunk carries `lineage: {document_id, version, chunk_index, source, ingested_at, embedding_model_version}`.
- Decision briefs carry the full list of `chunk_ids` that grounded them (`provenance[]`).
- Lineage is queryable: "which briefs cited this contract clause?"

---

## 4. Data Model

### 4.1 Canonical Document Model (ingest output)

```
Document {
  id: string                     // ULID, e.g. doc_01J…
  doc_type: enum[meeting, meeting_minutes, playbook, guideline,
                 decision, contract, template, postmortem, learning]
  source_system: string
  version: string                // semantic or source-native
  sha256: string
  title: string
  owner_team: string
  classification: enum[public, internal, confidential, legal-privileged]
  timestamps: { authored_at, ingested_at, effective_from, effective_to? }
  entities: [{ type, id, name, canonical_id }]
  acl: { allowed_teams: [], allowed_roles: [], public: bool }
  status: enum[active, superseded, archived, draft]
  raw_ref: s3://…/raw/<source>/<sha>
  chunks: [ChunkRef]
  extra: map                 // source-specific fields (e.g., meeting_id, launch_id)
}

Chunk {
  id: string                  // chunk_<sha256 of content>
  document_id: string
  chunk_index: int
  content: string             // up to chunk-size tokens
  role: enum[body, title, heading, decision_statement, learning_statement,
             clause, constraint, outcome, risk]
  section_path: string[]      // doc structure path, e.g. ["3.2", "Pricing"]
  tokens: int
  embedding: vector           // stored in vector collection, not in this JSON
  vector_id: string           // stable id for upsert
  provenance: { model_version, indexed_at }
}
```

### 4.2 Decision model (brief + lifecycle)

```
Decision {
  id: ULID
  title, statement, decision_class   // §8.1
  status: enum[draft, pending_review, in_approval, approved,
               rejected, executed, archived, superseded]
  requester: user
  context: { question, linked_docs[], custom_notes }
  brief: DecisionBriefRef
  approvals: [Approval]              // each: approver, role, step, status, decided_at
  provenance: [chunk_id]             // grounding chunks
  contradictions: [Contradiction]    // §9
  outcome: OutcomeRef?               // §11
  audit: [AuditEvent]
}

DecisionBrief {
  recommended_action: { action, rationale, confidence, alternatives[] }
  historical_precedents: [{ citation, similarity, relevance, how_it_went }]
  risk_factors: [{ risk, severity, likelihood, mitigation, source_chunk }]
  approval_flow: { required_gates: [], approvers_derived, sla_hours }
  contradiction_flags: [{ type, severity, past_learning, quote }]
  confidence: float
  model_info: { prompt_layer_versions, embedding_version, model_ids }
}
```

### 4.3 Vector collections

| Collection | Payload/chunks | Use case | Index type |
|-----------|----------------|----------|-----------|
| `docs_chunks` | All chunks (dense) | Semantic retrieval | HNSW on embedding + metadata filter |
| `docs_sparse` | Sparse vectors / BM25 index | Keyword recall | Inverted index |
| `decisions` | Decision summaries + outcomes | Precedent matching | HNSW |
| `learnings` | Extracted "learning statements" | Contradiction checks | HNSW |

`learnings` is a derived collection: the ingestion pipeline (or a periodic job) extracts high-signal statements — decisions with outcomes, post-mortem findings, playbook constraints — as single-purpose learning documents (§11.4).

### 4.4 ID scheme, versioning, retention
- ULIDs everywhere (time-sortable, collision-free).
- Documents and decisions are versioned; old versions remain queryable with `effective_to` filters so precedent lookups respect temporality ("what did we know then").
- Retention: raw vault immutable for 7 years (audit/compliance); vector indices kept in sync; redaction tokens reversible only inside raw vault with legal approval.

---

## 5. Embedding Strategy

### 5.1 Model selection & pluggability
- **Interface `Embedder`** with providers: OpenAI `text-embedding-3-large`, Cohere `embed-english-v3`, Azure OpenAI, Vertex `text-embedding-005`, open-source (BGE-M3, E5-large) via self-hosted inference.
- **Selection criteria** to be scored in the eval harness (§13): MTEB retrieval scores on our domain eval set, token cost, latency p95, hostability (for legal-privileged content).
- **Baseline default:** BGE-M3 (multilingual, supports dense+sparse+late interaction in one model) with `text-embedding-3-large` as fallback for English-heavy corpora. Final choice gated on eval §13.

### 5.2 Chunking strategy (content-aware)
| Source type | Strategy | Target size | Overlap |
|-------------|----------|-------------|---------|
| Meeting transcript | Speaker-turn aware; don't split a turn; speaker change = boundary | 300–500 tokens | 50 |
| Minutes | Section-aware (split on headings, decision/action lines) | 400 | 40 |
| Playbook/guideline | Rule-aware: one rule/constraint per chunk; heading-bound | 300 | 30 |
| Contract | Clause-aware: split on clause numbers, keep header sentence | 350 | 40 |
| Template | Section-aware | 400 | 50 |
| Post-mortem | Theme-aware (outcome, what-went-right, what-went-wrong) | 350 | 30 |
| Historical decision | Whole-decision block: statement+rationale+outcome together | 500 | 0 |
| Learning | Single statement per chunk | ≤150 | 0 |

Rationale: decision/learning statements must be self-contained to be matchable and citable; contracts must never have clause text spanning chunks; meeting transcripts benefit from speaker boundaries for attribution.

### 5.3 Embedding configuration
- Normalize embeddings (cosine similarity).
- Add a **prefix/suffix marker** by chunk `role` where the provider supports it (e.g., asymmetric search models) — encodes "this is a constraint," "this is an outcome."
- Metadata is *not* embedded; it lives in the payload for filtered search. Title/section path may be appended to content (max 3% tokens) to boost in-chunk signals.
- Dimensions pinned to model default (e.g., BGE-M3 = 1024); quantization: int8 or product-quantization acceptable if eval delta ≤1% nDCG.

### 5.4 Embedding versioning & re-embed
- Every index write stamps `embedding_model_version`.
- On model upgrade, run **dual-run** in eval harness, then re-embed via backfill in shards; old collection kept in read-only mode until the swap completes (blue/green).
- Hybrid merge (§6) tolerates mixed versions during migration.

### 5.5 Index parameters (HNSW, configurable)
- `ef_construction`: 200 (build-time recall), `M`: 32, `ef_search`: 128 (query-time).
- Partitioning/filter strategy: collection-level `tenant=think9`; filter on `acl` + `classification` at query time via payload index.
- Optional: text-vector (hybrid) index where supported (e.g., OpenSearch/Weaviate/pgvector with TSVECTOR).

---

## 6. Retrieval & Ranking

### 6.1 Query understanding
- Classify intent: `operational_question` vs `decision_brief` vs `contradiction_check` vs `precedent_search`.
- Rewrite query: extract entities (vendor, product, region), expand acronyms, produce 1 canonical + up to 2 alternative phrasings.
- Optionally retrieve related prior queries (from a query log) for expansion.
- Attach filters from entity extraction: `entities.vendor=X AND status=active`.

### 6.2 Candidate retrieval (recall phase) — hybrid, multi-strategy

| Strategy | Source | Weight (default) |
|----------|--------|------------------|
| Dense vector (cosine) | `docs_chunks` | 0.5 |
| Sparse / BM25 keyword | `docs_sparse` | 0.3 |
| Dense on `decisions` (precedent match) | `decisions` | 0.15 |
| Dense on `learnings` (contradiction/learning match) | `learnings` | 0.05 |

- Fetch top-K per strategy: `K_dense=20, K_sparse=10, K_decisions=10, K_learnings=10` (per collection), filtered by ACL/classification/status/temporality (`effective_from ≤ now ≤ effective_to`).
- Merge and **dedupe by document** (keep best chunk per document in the first stage, then allow re-ranking to pull siblings).
- Recency bias: add a small temporal boost (e.g., `score += 0.05 * exp(-days/365)`) configurable per doc_type — active playbooks beat archived ones, recent post-mortems beat old ones.

### 6.3 Reranking (precision phase)
- Cross-encoder reranker (interface `Reranker`; options: Cohere Rerank, cross-encoder models, LLM-as-judge fallback).
- Score top ~40 merged candidates → keep top 12–16.
- Reranker must respect the same ACL filter (already applied at recall).
- Output includes per-item relevance score used in prompt ranking and for thresholds.

### 6.4 Context packing
- Budget: **4,000 tokens** max context per decision brief (configurable; LLM window is 8k–200k).
- Allocation heuristic: 60% decision-relevant documents, 20% historical decisions with outcomes, 15% learnings, 5% structured metadata (entities, KPIs).
- Order by (relevance, recency). De-duplicate overlapping chunks (adjacent chunks of same section are merged if they fit).
- Tag every packed chunk with its citation `[doc_id, chunk_id, doc_type]` for the provenance block.
- Enforce a minimum-evidence gate: if top-1 relevance < threshold, respond with `insufficient_evidence` mode instead of fabricating (§8.5).

### 6.5 Relevance thresholds
- `RETRIEVE_OK`: top candidate score ≥ 0.55 (dense) — proceed to brief generation.
- `RETRIEVE_WEAK`: 0.35–0.55 — generate brief but mark `confidence: low` and require a human evidence-check gate.
- `RETRIEVE_NONE`: < 0.35 — return a structured "evidence gap" response; do not generate recommendations.

---

## 7. LLM Prompting Layers

### 7.1 Layer architecture

```
 L0 SYSTEM      → fixed safety/system persona (no user content, pinned, versioned)
 L1 ORCHESTRATOR → intent routing + tool planning (which retrievers to call)
 L2 RETRIEVER   → for each retrieval result: summarize/annotate chunk
 L3 SYNTHESIZER → ground answer/brief in the packed context (citation-aware)
 L4 DECISION BRIEF GEN → structured brief: action, precedents, risks, approval flow
 L5 CONTRADICTION FLAGGER → second-pass conflict detection vs learnings/decisions
 L6 FORMATTER   → JSON Schema–validated output; fails closed if invalid
```

- **Chain-of-thought with verification:** L3 → L5 run in two passes; the contradiction flagger gets the *draft brief + raw learnings*, not the model's own memory, so flags are evidence-based.
- **Model routing (via `LLMProvider`):** cheap fast model for L1/L2; frontier reasoning model for L3–L5; every layer pinned to a version and audited.
- **No hidden chain-of-thought in outputs:** briefs expose only the verdicts + citations, not intermediate reasoning.

### 7.2 L3–L4 Decision brief generation (core prompt contract)

```
ROLE: You are Think9's decision analyst. Ground EVERY claim in CONTEXT.
CONTEXT = <packed chunks with [doc_id, chunk_id, doc_type] tags>
QUESTION = <user operational question>
TASK: Produce the following fields (JSON):

1. recommended_action {
     action, rationale (≤3 sentences, must cite CONTEXT),
     confidence (0..1), alternatives[ {action, tradeoff} ] }
2. historical_precedents[ {
     citation, relevance (0..1), how_it_went (from outcome data if present) } ]
3. risk_factors[ { risk, severity (low|med|high|critical),
     likelihood (low|med|high), mitigation, source_chunk } ]
4. approval_flow { required_gates: [...], derived from decision_class rules },
5. contradictions[ ] — see L5.
6. evidence_gaps[ ] — notable questions CONTEXT cannot answer.

RULES:
- If an assertion is not supported by a cited chunk, put it in evidence_gaps instead.
- Never invent precedents, clauses, or outcomes.
- Confidence must decrease when context is thin or contradictory.
- Return ONLY valid JSON matching the schema below.
```

### 7.3 L5 Contradiction flagger (requirement #4)

Purpose: **flag when a new decision contradicts past learnings.**

Two-pass detection, evidence-based:
- **Pass A (learnings sweep):** embed the proposed `recommended_action` + `statement`; retrieve top-20 from `learnings` and top-20 from `decisions` (those with outcomes); ask L5 to classify each pair:
  - `consistent` / `contradicts` / `supersedes (with justification)` / `unknown`
- **Pass B (cross-check):** re-run the draft brief against retrieved past decisions and ask for explicit conflicts in approval conditions, constraints, or risk posture.

Output per flag: `{ type, severity, past_learning: {citation, quote}, conflict_reason, proposed_override_required }`.

Rules:
- A `contradicts` flag at severity high blocks automatic progression and forces an explicit gate (§8.4).
- `supersedes` requires the requester to attach a rationale; that rationale is captured and fed back as a future learning.
- L5 gets the raw chunks, never the model's memory of "typical practice."

### 7.4 Structured output & validation
- Every LLM call that returns data uses **JSON Schema** (`decision_brief.schema.json`, `contradiction.schema.json`) validated server-side; failed-validation retries once with schema re-prompt, then fails closed (no brief emitted).
- Where the provider supports tool/function calling (or constrained decoding), prefer it over free-text JSON.
- Prompt versions are stored with each brief (`model_info.prompt_layer_versions`) for reproducibility.

### 7.5 Guardrails
- Prompt injection defense: context chunks are delimited; user content cannot alter L0/L6.
- Output moderation + PII re-check on briefs before display.
- Citation integrity: brief's cited chunk IDs must exist in the packed context; anything else is dropped.
- Redaction: briefs never re-expose redacted tokens (placeholder guard test in CI).

---

## 8. Approval Gates (requirement #3 → approval flow)

### 8.1 Decision classification
Each decision is auto-classified into a **decision class** (validated/editable by requester):
`procurement`, `brand`, `contract`, `launch`, `pricing`, `vendor_selection`, `ops_change`, `compliance`.

### 8.2 Gate policy engine
- **Gate policies** are rules: `decision_class + risk_severity + amount/scope + contradiction_flags → required approvers + SLA`.
- Example rules:
  - `contract` + high severity risk → Legal + Procurement + CFO (SLA 48h).
  - `brand` + any contradiction severity high → Brand Ops + Head of Brand (SLA 24h).
  - `ops_change` + no flags + low risk → single team lead (SLA 8h).
- Policies live in `GatePolicyStore` (versioned, reviewable, auditable); approval flows are *derived*, not hard-coded in the LLM. The LLM proposes the flow; the engine enforces it.

### 8.3 Approval workflow
```
 brief.draft → GATE-1 requester-confirm → in_approval
   → for each gate in flow (ordered): notify approvers → collect (approve|request changes|reject)
   → all approved → status=approved → notify requester + execution hooks
   → any reject → status=rejected + reasons logged (fed to learning loop)
   → changes requested → new revision, back to brief
SLA exceeded → escalate to next role up, cc approver's manager.
```

### 8.4 Contradiction-driven gates
- High-severity contradiction → **mandatory gate** even if the class would normally skip approval; approver must explicitly record a `deviation_rationale`.
- Low-severity → informational flag on the brief; auto-approved path unchanged.

### 8.5 Insufficient evidence gate
- When `RETRIEVE_WEAK` or `RETRIEVE_NONE` (§6.5), the approval flow gains a mandatory **evidence-check step** (human verifies the brief or rejects asking for more context). The system never presents a confident brief on thin evidence.

### 8.6 Traceability & audit
- Every gate transition writes an `AuditEvent`: actor, action, decision_id, timestamp, reason, before/after status.
- Approvals are cryptographic-signature-ready (hash chain) for legal/audit use.
- Audit log is append-only and exported to the governance warehouse.

---

## 9. Contradiction & Precedent Signals (requirements #4 & #2)

| Signal | Source | How surfaced |
|--------|--------|--------------|
| Contradicts past learning | L5 vs `learnings` + `decisions` | Red flag on brief + mandatory gate |
| Supersedes prior decision | L5 with requester rationale | Amber flag + captured as future learning |
| Repeats known failure | outcome-tagged decisions matching | Red flag: "pattern resembles decision d_xxx which failed (metric)" |
| Reuses proven approach | outcome-tagged decisions matching | Green "precedent success" citation |
| No precedent | retrieval gap | Evidence-gap notice, lower confidence |

All flags include the exact chunk citation so reviewers can validate in seconds.

---

## 10. API Contracts

### 10.1 REST API (versioned `/v1`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/questions` | POST | Ask an operational question; returns grounded answer + citations |
| `/v1/decisions` | POST | Create a decision; triggers brief generation |
| `/v1/decisions/{id}` | GET | Fetch decision + brief + flags + status |
| `/v1/decisions/{id}/approve` `reject` `changes` | POST | Gate actions (role-checked) |
| `/v1/decisions/{id}/outcome` | PUT | Record outcome (§11) |
| `/v1/decisions?class=&status=` | GET | List/filter decisions |
| `/v1/search` | GET | Corpus search (used by thin client) |
| `/v1/precedents?query=` | GET | Precedent lookup |
| `/v1/ingest/{source}` | POST | Trigger ingestion for a source ref |
| `/v1/admin/reindex` | POST | Backfill/embed-version migration |
| `/v1/admin/eval/run` | POST | Run eval suite (§13) |
| `/v1/webhooks/ingest` | POST | Callback target for source systems (STT vendor, DMS) |

### 10.2 Example — create decision (request/response sketch)

```jsonc
// POST /v1/decisions
{
  "question": "Should we renegotiate the Okta enterprise renewal now or wait until Q4?",
  "class": "contract",
  "context": { "linked_docs": ["contract_okta_v3"], "notes": "counterparty signaled 8% hike" }
}

// 201 Created
{
  "decision_id": "dec_01JZ8X...",
  "status": "draft",
  "brief": {
    "recommended_action": { "action": "...", "confidence": 0.72, "alternatives": [] },
    "historical_precedents": [{ "citation": "[doc_x, chunk_12]", "relevance": 0.88, "how_it_went": "..." }],
    "risk_factors": [{ "severity": "high", "source_chunk": "[doc_y, chunk_4]" }],
    "approval_flow": { "required_gates": ["legal", "procurement", "cfo"], "sla_hours": 48 },
    "contradiction_flags": [{ "type": "contradicts", "severity": "high", "past_learning": "..." }],
    "confidence": 0.72,
    "model_info": { "prompt_layer_versions": {...}, "embedding_version": "bge-m3-2026.07" }
  },
  "provenance": ["doc_x_chunk_12", "doc_y_chunk_4"],
  "approvals": []
}
```

### 10.3 Events (outbound, via `EventBus`)
`document.indexed`, `decision.created`, `brief.generated`, `decision.flagged`, `approval.pending`, `approval.approved`, `approval.rejected`, `approval.escalated`, `decision.executed`, `outcome.recorded`, `learning.created`, `eval.completed`.

### 10.4 Portfolio intelligence API
The backend also exposes a cross-brand intelligence endpoint used by Slack and scheduled jobs:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/portfolio/intelligence` | POST | Aggregate cross-brand challenges, score opportunities/risks, and emit execution triggers |

**Aggregation logic**
- Group corpus observations by shared `vendor`, `ingredient`, or `theme`.
- Add `region` when a weather-related signal appears in the same corpus slice, so supply shocks can be tracked as shared exposure.
- Require at least 3 distinct brands before a cluster becomes actionable.
- Prefer active decisions, negotiations, vendor docs, playbooks, postmortems, and learnings.
- Use document metadata first; fall back to text heuristics when metadata is sparse.

**Opportunity scoring**
- Score clusters on brand coverage, brand depth, document breadth, recency, type diversity, repeated signal strength, and severity.
- Cross-brand vendor and ingredient clusters get a higher base weight because they are the strongest consolidation candidates.
- Sustainability messaging and brand-positioning themes are scored as coordination opportunities even when no procurement action is needed.
- Monthly reporting reuses the same score and rolls up estimated portfolio value created from bundled RFQs, MOQ consolidation, and campaign coordination.

**Execution triggers**
- `route_bundled_rfq` when 3+ brands share the same vendor or ingredient and the score crosses the configured threshold.
- `notify_brand_leads` when 3+ brands show the same brand or messaging trend.
- `flag_portfolio_risk` when concentration risk, high-severity supplier issues, or weather/region risk threatens multiple brands.
- The monthly report is generated by the same backend service and can persist Slack alerts for each trigger.

---

## 11. Outcome Tracking & Continuous Learning (requirement #5)

### 11.1 Outcome intake
- Two paths: (a) structured form/API on decision execution closeout, (b) scheduled sweep that parses execution-status reports and post-mortems to back-fill outcomes.
- Outcome record: `{ decision_id, result (success|partial|failure|superseded), metric_deltas[] {metric, actual, target, source}, narrative, recorded_at, recorded_by, evidence_ref }`.

### 11.2 KPI attribution
- Outcome metrics mapped to canonical KPIs (MRR, contract value, CAC, launch NPS, brand recall, delivery SLA). Where a decision links to a KPI, the outcome enriches the decision's embedding payload so precedent matching can weigh "how_it_went."

### 11.3 Learning-doc generation
- On `outcome.recorded`, a **learning document** is synthesized: `{statement, decision_ref, outcome, kpis, causal_notes}`.
- Only learnings above a quality threshold (eval + human confirm on first N, then auto) are embedded into the `learnings` collection.
- Learnings carry `effective_from = outcome date` and `status = active`, so contradiction checks respect when knowledge was gained.

### 11.4 Feedback signals into retrieval & prompt quality
- **Retrieval feedback:** when users rate a brief poor / mark evidence wrong, the query+doc pairs are logged to the eval harness as negative training/eval data.
- **Contradiction correction:** when a human overrides a flag (accepts a contradiction with rationale), that pair is stored and used to fine-tune the flagger or adjust thresholds.
- **Periodic distillation:** quarterly job summarizes repeat patterns into playbook amendments (draft for human review, never auto-published).

---

## 12. Security, Compliance, Privacy

- **AuthN/AuthZ:** IdP (SSO/SAML/OIDC) + role-based access; team + role + classification checks at API and at vector-store filter level (defense in depth — retrieval never sees non-allowed chunks).
- **Legal-privileged & confidential content:** separate collection with stricter ACLs, no public default; redaction enforced at ingest; raw vault access requires dual authorization.
- **Data residency:** configurable per-deployment (BYO stack allows EU/US residency isolation).
- **Encryption:** TLS in transit; KMS-managed keys at rest; vector store SSE.
- **Audit:** append-only audit log; approvals hash-chained; `export` endpoint for regulators.
- **Model risk:** LLM providers must sign data-usage terms (no training on our data) or run self-hosted for privileged content; this is a hard procurement gate.

---

## 13. Evaluation & Quality (eval harness)

### 13.1 Offline eval
- **Gold set:** ~200 seeded Q/A-brief pairs built by a cross-functional panel from real historical decisions; grows with every verified outcome.
- **Metrics:** retrieval nDCG@10, recall@20; brief quality via LLM-as-judge + human spot-check (faithfulness, citation accuracy, completeness); contradiction flag precision/recall vs labeled set.
- **Regression gate in CI:** no model/embedding/prompt change ships if it drops any core metric ≥2%.

### 13.2 Online monitoring
- Brief quality feedback rating; citation-click-through; approval rejection rate as a proxy for brief usefulness; flag override rate.
- **Drift monitoring:** embedding drift, LLM output drift (temporal leakage check: does a brief "know" something it couldn't have known then?), and retrieval coverage gaps.

### 13.3 Threshold tuning
- `RETRIEVE_*` thresholds and rerank cutoffs tuned against the gold set; versioned with the eval run.

---

## 14. Provisioning / Deployment (IaC outline)

- **IaC:** Terraform modules per capability (`ingest`, `retrieve`, `generate`, `governance`, `ops`) — provider-agnostic where possible (e.g., S3 vs GCS behind a `storage` module).
- **Environments:** `dev`, `staging`, `prod`. Data is synthetic in dev; staging mirrors prod structure with sampled anonymized docs.
- **Provider abstractions (the BYO layer):**

| Concern | Interface | Reference implementations |
|---------|-----------|---------------------------|
| Object storage | `ObjectStore` | S3, GCS, Azure Blob |
| Event bus | `EventBus` | SNS/SQS, Pub/Sub, Event Grid, Kafka |
| Vector store | `VectorStore` | pgvector, OpenSearch, Weaviate, Qdrant, Milvus, Pinecone |
| Sparse index | `SparseIndex` | OpenSearch BM25, Weaviate BM25, Tantivy |
| Embedder | `Embedder` | OpenAI, Cohere, Vertex, BGE-M3 self-hosted |
| Reranker | `Reranker` | Cohere Rerank, cross-encoder, LLM-as-judge |
| LLM gateway | `LLMProvider` | OpenAI, Anthropic, Gemini, Bedrock, self-hosted vLLM |
| Orchestrator | `PipelineRunner` | Step Functions, Airflow, Prefect, Temporal |
| Secrets | `SecretStore` | Vault, AWS Secrets Manager, GCP SM |

- **Cost guardrails:** LLM token budgets per request, per-user; caching of embedding calls; batch embed during backfills.
- **Scalability:** ingest workers scale per source; retrieval is stateless and scales horizontally; vector store is the horizontal scaling boundary.

---

## 15. Observability & Runbooks

- **Metrics:** ingestion lag, DLQ depth, embed latency, retrieval p95, rerank p95, LLM p95 + token cost, brief generation success rate, gate SLA breach count, outcome capture rate, eval core metrics.
- **Traces:** distributed tracing keyed on `decision_id`/`document_id` across ingest → retrieve → generate → approve → outcome.
- **Runbooks (key ones):**
  1. **Index drift / corrupted vector store** → restore from snapshot (daily vector snapshot + raw vault rebuild path).
  2. **Embedding model vendor outage** → failover `Embedder` to secondary provider (dual embeddings maintained or lazily generated).
  3. **LLM provider outage / degradation** → route to backup provider at same layer version; if none, fail closed (briefs queue, no silent downgrade).
  4. **Retrieval quality drop detected by eval** → pin last-good prompt/embedding version, open drift investigation.
  5. **Gate SLA breach** → escalation automation (§8.3) + on-call.
  6. **Security incident / PII leak** → revoke raw-vault access, quarantine collection, run redaction re-check over briefs.

---

## 16. Phase Plan

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| P0 (wk 1–4) | Corpus inventory, canonical model, ingest for minutes + playbooks, vector store v1, search API | 3 sources indexed; retrieval demo |
| P1 (wk 5–10) | All source adapters; hybrid retrieval + rerank; eval harness + gold set v1 | nDCG@10 ≥ target; thresholds set |
| P2 (wk 11–16) | Brief generation layers L3–L6; structured outputs; provenance | Human panel scores briefs ≥ 4/5 faithfulness |
| P3 (wk 17–22) | Contradiction engine; gate policy engine + approval workflow | Flag precision ≥ 80% on labeled set; gates enforce |
| P4 (wk 23–28) | Outcome tracking + learning loop; drift monitoring | Outcome capture ≥ 80% of executed decisions |
| P5 (wk 29–32) | Hardening: audit chain, redaction pass, compliance export; playbook distillation pilot | Audit/compliance sign-off |

---

## 17. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hallucinated precedent/citation | Trust collapse | Mandatory citation integrity check (§7.4), evidence-gap mode (§6.5) |
| Legal content leakage | Regulatory/legal exposure | ACL-at-query defense, redaction, separate privileged collection, vendor data-usage clauses |
| Stale learnings treated as current | Wrong advice | Temporality filters, effective_from/to, superseded status |
| Contradiction flagger noise | Approval fatigue, bypass | Precision-first tuning, human override feedback loop (§11.4) |
| Embedding/model vendor lock-in | Portability risk | Interface layer + dual-run eval + blue/green re-embed |
| Outcome capture decay | Learning loop stalls | Automated outcome sweeps, KPI attribution hooks at execution |
| Prompt injection via ingested docs | Misbehavior | Chunk delimiting, L0/L6 pinning, output moderation |

---

## 18. Open Questions for Review
1. Does Think9 want a human review on every auto-generated learning doc, or only flagged ones?
2. Are there existing compliance regimes (SOC2, DORA, finance-specific) that dictate audit retention beyond 7 years?
3. Which IdP/RBAC source of truth will govern the approval gate actor resolution?
4. Confirm the eval gold-set owners and the 20-pair/month contribution cadence.
5. Does `supersede` require the original decision owner's consent before it takes effect?

---

## 19. Glossary
- **Chunk** — atom of retrieval and citation; a bounded slice of a document.
- **Decision brief** — generated artifact with action, precedents, risks, approval flow, flags.
- **Gate** — required approval step; enforced by policy engine, not by the LLM.
- **Learning document** — single-statement knowledge derived from outcomes; feeds contradiction checks.
- **Precedent** — prior decision with outcome, used to support or warn against a proposed action.
- **BYO layer** — provider-agnostic interfaces listed in §14.

---

*Appendix A: decision_brief.schema.json, appendix B: contradiction.schema.json, appendix C: per-source chunking configuration table — maintained alongside this spec in `/docs/`.*
