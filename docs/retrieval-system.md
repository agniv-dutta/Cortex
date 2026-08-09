# Think9 Decision Intelligence — Retrieval System

**Version:** 1.0
**Status:** Draft for review
**Companion docs:** `decision-intelligence-spec.md` (§5 embeddings, §6 retrieval/ranking), `decision-intelligence-mvp.md`, `agentic-workflow.md` (Agent 2), `ingestion-system.md` (chunking/embedding settings), `prompts.md`.

This doc is the deep-dive on **institutional knowledge retrieval**: chunking, model selection, ranking, failure handling, query expansion, vector DB choice, parameters, and benchmarks.

---

## 1. Chunking Strategy (focus: meeting notes)

Meetings are the highest-volume, highest-variance source. Three strategies answer "how to split", used in combination — a **multi-level** approach, not a single choice.

### 1.1 Strategy A — By discussion topic (preferred, when structure exists)
- **How:** LLM topic-segmentation pass on the transcript (or use native Zoom "topics"/agenda if present). Boundaries at topic changes; a topic spans multiple speaker turns.
- **When:** any meeting with a stable agenda or >4 topics.
- **Pros:** retrieval returns whole-topic units — the best unit for "what did we decide about X".
- **Cost:** one LLM pass per meeting at ingestion (not query time).

### 1.2 Strategy B — By decision (highest-value chunks)
- **How:** each extracted decision is stored as its own self-contained `decision` chunk: statement + rationale + owners + deadlines + (if known later) outcome. These chunks are the backbone of precedent matching.
- **When:** always. Decisions are extracted during ingestion (§2.1 of ingestion spec); the transcript chunks reference them via `decision_ids[]`.
- **Why:** precedent retrieval must return *decision-shaped* units, not buried sentences.

### 1.3 Strategy C — By time window (deterministic fallback)
- **How:** fixed 15-minute windows (or 500-token windows) when no topic structure can be derived and speaker-turn data is missing.
- **When:** low-quality/raw transcripts, no speaker map, no agenda.
- **Pros:** deterministic, cheap. **Cons:** lower precision — mitigated by metadata and the `decision_ids[]` anchors.

### 1.4 Recommended composition per meeting
```
meeting_summary  → 1 chunk (whole, ≤800 tokens)
transcript       → topic chunks (Strategy A) or time-window chunks (Strategy C)
decision docs    → 1 chunk each (Strategy B)   ← the precedent backbone
```

### 1.5 Chunk size & overlap

| Chunk type | Target size | Overlap | Min | Max |
|-----------|-------------|---------|-----|-----|
| Topic chunk (A) | 300–500 tokens | 50 | 100 | 700 |
| Decision chunk (B) | ≤ 200 tokens | 0 | 50 | 500 |
| Time-window chunk (C) | 500 tokens | 50 | 200 | 800 |
| Meeting summary | ≤ 800 | 0 | — | 800 |

Rationale: retrieval units must be large enough to carry context, small enough to be one citation. Decision chunks are deliberately compact so a precedent citation points at *one* decision.

### 1.6 Metadata attached to every meeting chunk

```jsonc
{ "meeting_id": "mtg_01…", "date": "2026-08-08", "doc_type": "meeting",
  "topic": "Vendor negotiation", "speaker": "…", "attendees": ["U123","U456"],
  "brands": ["protein"], "functions": ["supply_chain"],
  "agenda_items": ["MOQ", "pricing"],
  "decision_ids": ["dec_01…", "dec_02…"],
  "outcome": null,                 // populated later via outcome loop
  "status": "active",
  "acl": { "allowed_teams": ["supply_chain"], "public": false } }
```

Metadata is **filtered** at query time, never embedded (spec §5.3). `outcome` is back-filled asynchronously when the decision outcome is recorded (§11 ingestion spec), so a meeting chunk about a decision gains outcome context retroactively.

---

## 2. Embedding Model Selection

### 2.1 Candidate models

| Model | Dims | Multilingual | Self-host | Approx. cost /1M tok | MTEB-ish | Notes |
|-------|------|--------------|-----------|----------------------|----------|-------|
| OpenAI `text-embedding-3-large` | 3,072 | Good | No | $$$ | High | Quality ceiling; can project to lower dims |
| OpenAI `text-embedding-3-small` | 1,536 | Good | No | $ | Good | **MVP default** (cost/quality sweet spot) |
| Cohere `embed-english-v3` | 1,024 | Good | No | $$ | Good | Retrieval-tuned; supports embedding fine-tuning; 512-token chunk default |
| BGE-M3 | 1,024 | **Excellent** | Yes | Free (self-host) | Good | Dense+sparse+late-interaction in one model; **privileged-content profile** |
| Local Llama (e.g., Llama-3 embeddings) | 4,096 | Fair | Yes | Free | Good | Only for strict data-residency; heavier ops |

### 2.2 Why this choice for Think9
- The corpus is **English-dominant business/consumer-goods prose**: negotiations, MOQ/pricing terms, brand voice, post-mortems. It is not deeply technical or low-resource-language — top-tier MTEB models are more than sufficient; the bottleneck will be chunking quality and ranking, not the embedding ceiling.
- **Dual profile recommendation:**
  - **Primary (default):** OpenAI `text-embedding-3-large` for the full corpus when budget allows; `text-embedding-3-small` as the MVP default.
  - **Privileged (legal/confidential):** **BGE-M3 self-hosted** so confidential content never leaves the VPC (§12 spec). Same interface (`Embedder`), different profile per ACL tier.
- **No local Llama initially:** self-hosting adds GPU ops without a retrieval win at 6–20k chunk scale. Revisit only for strict residency requirements beyond the BGE-M3 profile.

### 2.3 Fine-tuning — is it needed?
**Not initially. Do it only if the eval harness proves a domain gap.**

Why not by default:
- Think9 jargon (MOQ, co-pack, protein/wellness SKUs, "walk-away") is *not opaque to embeddings* — these terms co-occur richly in the corpus, which is what unsupervised embeddings exploit.
- Fine-tuning needs labeled `(query, relevant_chunk)` triplets; at 6–20k chunks the gold set (200 Q/A pairs, §13 spec) is too thin to train embeddings without overfitting.
- Risk: over-tuning to a small set makes retrieval worse on out-of-set queries.

Ordered remediation ladder if eval (nDCG@10) shows a domain gap:
1. **Role/prefix markers + metadata filters** (§1.6) — cheapest, usually closes most of the gap.
2. **Query expansion** (§5) + better rewrite — improves recall without retraining.
3. **Reranker upgrade** (cross-encoder) — improves precision without retraining.
4. **Cohere embedding fine-tuning** on an accumulated triplet set (requires ~1–3k labeled pairs, so only after Phase 2 volume).
5. Local fine-tune of BGE-M3/Llama only if (4) impossible and residency requires self-host.

Gate: any fine-tuning must beat the current profile by ≥2% nDCG@10 on the gold set to ship (same bar as prompt changes).

---

## 3. Vector Search Ranking

### 3.1 Two-stage pipeline
```
Stage 1 (candidate generation)   filters → hybrid score → top-40
Stage 2 (re-rank)                cross-encoder → top-12–16 for context pack
```

### 3.2 Stage 1 — hybrid base score

```
hybrid_score = w_sem · norm(semantic_cosine)
             + w_bm  · norm(bm25_ts_rank)
             + w_cat · category_boost(chunk, query)
             + w_age · freshness_weight(chunk, query)

default weights:  w_sem = 0.50   w_bm = 0.25   w_cat = 0.15   w_age = 0.10
```
- `norm(·)`: min-max scaled within the candidate set (avoids BM25/dense score-scale mismatch).
- Hard filters applied *before* scoring: ACL, classification, `status IN (active)`, `effective_from ≤ now ≤ effective_to`.
- Penalty: `-0.30` flat on `status = superseded/archived` in as-of queries; excluded entirely for default retrieval.

### 3.3 Category boost (category → doc_type)

| Query category | Boosted doc_types | Boost |
|----------------|-------------------|-------|
| procurement | vendor, negotiation, contract, playbook | +0.20 |
| brand | playbook, postmortem, meeting, feedback_summary | +0.15 |
| product | launch, postmortem, meeting, feedback_summary | +0.15 |
| hr | meeting, guideline | +0.15 |
| legal | contract, template, decision | +0.20 |
| ops | meeting, decision, guideline | +0.10 |

Boost applies to `w_cat` term; it steers recall toward the right source types, never overrides a genuinely relevant cross-category hit.

### 3.4 Freshness weighting (recent decisions weigh higher)

```
freshness_weight = exp( -λ · days_since / half_life_doc_type )

half-life by doc_type:
  playbook rules        30 days   (rules decay fast; a 2-year-old rule is suspect)
  decisions/precedents  365 days  (outcome knowledge ages slowly)
  meetings              180 days
  contracts             730 days  (terms are durable until superseded)
  post-mortems          365 days
λ (decay steepness) = 1.0 default; tune per doc_type.
```
**Important:** freshness is a *tie-breaker and recall steers* — never allowed to outweigh a high-relevance old hit. Cap the `w_age` term at 0.10 so a 0.9-similarity 2019 precedent still beats a 0.4-similarity 2026 chunk. Temporal *correctness* (what was known at time T) is handled by as-of filters, separate from recency preference.

### 3.5 Stage 2 — re-ranking
| Approach | Tool | Latency | Cost | Use |
|----------|------|---------|------|-----|
| Cross-encoder | Cohere Rerank or `bge-reranker-v2-m3` | +60–150ms | $$ | **Production default** for briefs |
| LLM relevance judgment | in-context scoring via `gpt-4o-mini` | +300–600ms | $ | Eval-only, or fallback when reranker down |
| None (hybrid score only) | — | 0 | $ | Search UI (dashboard), MVP search |

- Re-rank top **40** candidates, keep top **12–16** for the context pack (§6.4 spec).
- Cross-encoder re-scores each `(query, chunk)` independently; scores normalized and used for context-pack ordering and the `RETRIEVE_*` thresholds.

### 3.6 Thresholds
```
RETRIEVE_OK   ≥ 0.55  → generate full brief
RETRIEVE_WEAK 0.35–0.55 → brief + `confidence: low` + human evidence-check gate
RETRIEVE_NONE < 0.35  → evidence-gap response (no fabrication)
```
Thresholds are tuned on the gold set and versioned with the eval run (spec §13.3).

---

## 4. Retrieval Failure Handling

### 4.1 Failure ladder
| Condition | Behavior |
|-----------|----------|
| Top-1 relevance < 0.35 (no signal) | **Evidence-gap response**: state that the corpus has no strong match; list what would be needed (e.g., "no prior MOQ negotiation with ingredient vendors; no playbook rule on MOQ"). Offer broadened search. **Do not** generate a recommendation. |
| Coverage present but weak (0.35–0.55) | Generate brief at `confidence: low`; add `missing_context_alerts`; route to human evidence-check (H3/H4 in agentic spec §7). |
| Dense search empty, BM25 empty | Retry once without category filter + brand `all` + doubled recency window. Still empty → evidence-gap response. |
| Source-level gap (e.g., no decisions in a whole category) | Surface a **corpus gap** to the data team (creates an ingestion task, e.g., "decision log missing legal outcomes 2023"). |

### 4.2 Fallback to general decision principles
- Maintain a small, curated **`general_principles`** corpus (generic frameworks: negotiation best practices, MOQ/forecast heuristics, risk-matrix methodology). Clearly tagged `source: general_principles`.
- **Rules:**
  - General-principle chunks may be used **only to enrich the evidence-gap response**, never as grounds for a confident recommendation.
  - Any brief that leans on general principles must show `evidence_type: general_principle` on each such citation, mark those precedents `outcome: null`, and cap overall brief confidence at **0.5**.
  - General principles never appear in `contradiction` checks (they are not institutional truth).

### 4.3 Novel decision type alert
- Trigger: `RETRIEVE_WEAK` or `RETRIEVE_NONE` **plus** zero matching decisions with known outcomes.
- Behavior: tag the brief `decision_type: novel`; notify the requester + category SME ("This appears to be a novel decision type — no institutional precedent found"). Route to triage (H8, agentic spec §7) and log as a **learning candidate** once executed (so the second instance of this decision type is no longer novel).

---

## 5. Query Expansion

### 5.1 Goal & guardrail
Expand the query to *related retrieval intents* to raise recall — while never changing the user's intent or category. The **original query always keeps the highest weight**; expansions are recall-only, excluded from the final `category`/`urgency` signals.

### 5.2 Expansion structure
```
query_expansion = {
  canonical: "Should we drop this vendor?",
  entities:  { vendor: "Vendor X" },
  sub_queries: [ "Vendor X performance issues and SLAs",
                 "Historical vendor transitions and outcomes",
                 "Procurement policy for vendor changes and offboarding" ],
  related_sources: ["negotiation", "contract", "decision", "playbook", "postmortem"],
  negative_hints: []        // e.g., avoid unrelated brand-launch docs
}
```

### 5.3 Expansion logic (three mechanisms, applied in order)

1. **Entity-anchored expansion (deterministic).** Use extracted entities (vendor, brand) + a per-category relationship map:
   - `vendor` → { "performance issues", "historical transitions", "policy for vendor changes" }
   - `brand` → { "brand playbook", "voice and tone", "launch constraints" }
   - `product` → { "launch postmortems", "supply readiness" }
   This alone turns "drop this vendor" into the three example sub-queries above.

2. **Synonym / acronym expansion (lexicon).** Small maintained lexicon: "drop"→{terminate, offboard, remove, cut}, "MOQ"→{minimum order quantity, order minimum}, "walk-away"→{reject, no-deal}. Applied at recall only.

3. **LLM query expansion (optional, high-signal).** `gpt-4o-mini` at temp 0 generates up to 3 sub-queries + `related_sources`, schema-validated. Guardrails in the prompt: "Stay within the same category and intent; do not broaden to unrelated topics; do not invent facts." **Skip in MVP** if deterministic expansion (1+2) meets recall targets.

### 5.4 Where expansion is used
- Sub-queries run in parallel through Stage-1 retrieval; results merged by `hybrid_score` with the canonical query weighted ×1.0 and each sub-query ×0.6.
- Expansion feeds **recall** only — the re-ranker (Stage 2) sees the merged candidate set and applies precision on top. Category/dedup filters (spec §6.2) run after merge.
- Expansion candidates never inflate confidence: `RETRIEVE_*` thresholds are computed from the *canonical query* top result, not the best expanded hit.

---

## 6. Vector DB Choice

### 6.1 Comparison

| Criterion | pgvector (Postgres) | Qdrant | Weaviate | Milvus | Pinecone | OpenSearch |
|-----------|--------------------|--------|----------|--------|----------|-----------|
| Ops burden | Low (uses existing Postgres) | Low | Med | Med–High | None (SaaS) | Med |
| Scale ceiling | ~1–5M vectors / single node | 100M+ (distributed) | 100M+ | 100B+ | 100M+ | 10M+ |
| Hybrid dense+sparse | ✅ (pgvector + TSVECTOR) | ✅ (BM25 sparse) | ✅ (BM25) | ✅ | ✅ (hybrid API) | ✅ (native BM25) |
| Self-host / residency | ✅ | ✅ | ✅ | ✅ | ❌ (SaaS) | ✅ |
| Multi-tenancy / ACL filters | ✅ (SQL filters) | ✅ (payload filters) | ✅ | ✅ | ✅ | ✅ |
| Latency @ 1M vectors (p95) | ~5–15ms | ~1–5ms | ~2–8ms | ~1–5ms | ~2–10ms | ~10–30ms |
| Cost at Think9 scale (~20k vectors) | ~free (existing DB) | $ | $–$$ | $$ | $$$ | $$ |
| Extra infra to run | None | 1 cluster | 1 cluster + indexer | Zookeeper etc. | None | 1 cluster |

*(Latency figures are planning references at ~1M vectors on typical cloud hardware; measure in your environment — see §8.)*

### 6.2 Recommendation
| Phase | Choice | Why |
|-------|--------|-----|
| **MVP (Phase 1)** | **pgvector** | Corpus is ~6–20k chunks. Zero extra infra, SQL joins for provenance (`brief_chunks`), one DB to back up. Hybrid = pgvector + TSVECTOR in one query. |
| **Scale-up (Phase 2+)** | **Qdrant or Weaviate** (BYO, self-host) | Horizontal scaling, native hybrid (BM25 + vector) in one index, strong payload filtering for ACL. Pick the one that wins the §8 benchmark at target volume. |
| If fully managed is preferred | Pinecone | Skip ops, pay premium; note data-residency limits for privileged content. |

The `VectorStore` interface (spec §14) makes the MVP→Phase 2 swap a config change, not a rewrite.

### 6.3 Search parameters (pgvector reference)

```sql
CREATE INDEX idx_chunks_embedding ON chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 32, ef_construction = 200);

-- query-time: SET hnsw.ef_search = 128;  (higher = more recall, more latency)
```
| Parameter | Value | Note |
|-----------|-------|------|
| `M` (HNSW neighbors) | 32 | 16–64 range; 32 is balanced at this scale |
| `ef_construction` | 200 | Build-time; raise for larger corpora |
| `ef_search` | 128 (dynamic) | 40–400 range; tune against the gold set |
| Distance | cosine | Embeddings normalized |
| `lists`/probes (IVF) | n/a | HNSW is the default; IVF only if memory-bound |
| Batch writes | 64/request | Ingestion spec §3.3 |

---

## 7. Search Flow (end-to-end, one query)

```
query → A1 router → category/brands/entities/urgency
      → query expansion (§5) → sub-queries
      → Stage 1: filtered hybrid search (dense + BM25 + category boost + freshness)
      → merge + dedupe by document
      → Stage 2: cross-encoder re-rank top-40 → top-12–16
      → thresholds → RETRIEVE_OK / WEAK / NONE
      → context pack (§6.4 spec) → brief or evidence-gap
```

---

## 8. Performance Benchmarks (to measure, with planning targets)

**Load:** ~6–20k chunks Phase 1; target headroom to 1M chunks Phase 2+.

| Metric | MVP target (Phase 1) | Phase 2 target |
|--------|----------------------|----------------|
| Retrieval recall@20 | ≥ 0.85 | ≥ 0.90 |
| nDCG@10 (gold set) | ≥ 0.75 | ≥ 0.82 |
| P95 end-to-end query (search) | < 1.0 s | < 800 ms |
| P95 Stage-1 hybrid | < 60 ms | < 150 ms @ 1M |
| P95 re-rank (40 items) | < 200 ms | < 150 ms |
| Brief generation end-to-end | < 30 s (async ack) | < 15 s |
| Index build (20k chunks) | < 5 min | < 30 min @ 1M |
| Storage (embeddings, 20k × 1,536 dim) | ~130 MB | ~6 GB @ 1M |

**Benchmark methodology:** gold set from §13 spec; run every DB candidate against the same HNSW params + hybrid weights; report nDCG@10, recall@20, p95 latency, and build time. A candidate must beat the incumbent by ≥2% nDCG or ≥30% latency to justify a swap.

**Tuning loop:** eval harness (§13 spec) drives all knobs — hybrid weights, half-lives, category boosts, thresholds. Every change is versioned with an eval run and gated on the ±2% rule.

---

## 9. Open Questions

1. Is the `general_principles` corpus (curated generic knowledge) approved as a content source, or should Phase 1 have zero non-institutional content?
2. Should freshness half-lives be tuned per brand category (e.g., protein vs. wellness) or global per doc_type?
3. Confirm re-ranker budget: Cohere Rerank (paid) vs self-hosted `bge-reranker-v2-m3` (free, +GPU ops) as the Phase 2 production default.
4. Does the P&L-sensitive corpus need query-time temporal "as-of" fidelity in Phase 1, or is `active`-only sufficient until the audit requirements land?
