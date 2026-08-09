# Think9 Decision Intelligence — Cost & Performance Analysis

**Version:** 1.0
**Status:** Draft for review
**Companion docs:** `decision-intelligence-mvp.md`, `retrieval-system.md`, `roadmap-mvp.md`, `agentic-workflow.md`.

This doc answers the economics of the MVP and early production: model choice, vector DB, caching, sync/async trade-offs, monitoring, and ROI. All prices are **planning references (as of 2026)** — re-verify against current provider rate cards before committing; the *structure* of the analysis is what matters.

---

## 1. LLM Choice

### 1.1 Reference pricing

| Model | Use tier | Input $/1M tok | Output $/1M tok | Notes |
|-------|----------|----------------|-----------------|-------|
| `gpt-4o-mini` / Claude Haiku | cheap | ~$0.15 / ~$1.00 | ~$0.60 / ~$5.00 | routing, classification, escalation |
| `gpt-4o` | premium | ~$2.50 | ~$10.00 | brief synthesis fallback |
| **Claude Sonnet 4** | premium | ~$3.00 | ~$15.00 | **brief synthesis + validation (recommended)** |
| `text-embedding-3-small` | embedding | $0.02 | — | MVP embedding |
| `text-embedding-3-large` | embedding | $0.13 | — | quality profile |
| BGE-M3 (self-host) | embedding | ~free/token | — | + GPU/cpu ops; residency only |

### 1.2 Model tiering — the core recommendation

**Two tiers, never one model for everything:**

| Tier | Models | Tasks | Why |
|------|--------|-------|-----|
| **Cheap** | `gpt-4o-mini` (or Haiku) | Query router, escalation criteria, meeting summarization, query expansion, relevance scoring (eval) | High-volume, low-complexity; accuracy ≥ 95% at 1/20th the cost |
| **Premium** | **Claude Sonnet 4** (primary), `gpt-4o` (fallback) | Decision brief synthesis, contradiction validation, risk assessment | Low-volume (~5–20/day), high-value artifacts that humans act on. A bad brief wastes expensive approver time, not just tokens |

**Cost vs quality verdict:**
- Premium model spend on briefs is ~$0.05 per brief — rounding error even at 1,000 briefs/month (~$50).
- A mis-routed query or noisy classification costs far more in downstream recovery than a cheap model ever saves. **Never route with a frontier model; never synthesize with a mini model.**

### 1.3 Local open-source embeddings — cost verdict
| Factor | Number |
|--------|--------|
| Corpus cost to embed (2M tokens) with `text-embedding-3-small` | **~$0.04 one-time** |
| New content/month (50 transcripts ≈ 500k tokens) | **~$0.01/month** |
| Full re-embed on model change | **~$0.04** |
| Self-hosting BGE-M3 on GPU | **~$150–300/month infra + ops** |

**Conclusion:** at Think9's scale, embedding cost is *negligible* with a hosted API. Self-hosting saves pennies and adds GPU ops — **only justified by data-residency/compliance**, not cost. Revisit at 100M+ tokens *if* re-embedding monthly becomes a thing (even then it's ~$2–20/month). (See §6 scaling curve.)

---

## 2. Vector DB Choice

### 2.1 Option comparison

| Option | Ops | Monthly cost* | Scale headroom | Latency @1M vec | Fit |
|--------|-----|---------------|----------------|-----------------|-----|
| **pgvector (Postgres)** | Low (reuse DB) | $50–100 (RDS) | ~1–5M vectors/single node | 5–15ms p95 | **MVP → Phase 2** |
| Qdrant / Weaviate self-hosted | Med | $150–400 (infra) | 100M+ (distributed) | 1–8ms p95 | Phase 3 scale-up |
| Weaviate Cloud | None | ~$75+/mo, scales | 100M+ | 2–8ms p95 | If ops-constrained |
| Pinecone (SaaS) | None | free tier (~100k vec); $70+/mo | 100M+ | 2–10ms p95 | If fully managed preferred |
| **Milvus (self-host)** | **High** (etcd, MinIO, workers) | $200–600 | 100B+ | 1–5ms p95 | Only at extreme scale; overkill for Think9 |

\* planning references; exclude egress/dedicated capacity nuances.

### 2.2 Decision
- **MVP + early production: pgvector.** 6–20k chunks now; even "100M tokens of institutional knowledge" is only ~330k chunks (§6) — inside pgvector's single-node envelope.
- **When to move:** >1M chunks, multi-region, or sustained p95 latency requirements below ~50ms at that scale. Then: **Qdrant/Weaviate self-hosted** (BYO posture) or **Pinecone** if the team wants zero vector ops. **Milvus only if you plan for billions of vectors** — the ops cost is not justified earlier.

### 2.3 Latency requirements (channel-driven)
| Channel | Requirement | Budget breakdown |
|---------|-------------|------------------|
| **Slack quick query (real-time)** | **p95 < 5 s** | router 0.3s + retrieval 0.1s + generation 2–3s |
| **Slack decision brief** | ack < 2 s; brief reply ≤ 30 s | async job (premium) |
| **Web dashboard search** | p95 < 1 s | retrieval only + light LLM |
| **Scheduled email reports** | ≤ 60 s runtime, delivered 6:00 | full async batch, no latency constraint |

Retrieval itself (even hybrid + rerank) is 100–300ms — **never the bottleneck**; the LLM is. This is why the sync/async split (§4) matters more than vector-DB latency.

---

## 3. Caching Strategy

Three cache levels — distinct objects, distinct invalidation:

| Level | Cache key | What's stored | TTL | Invalidation | Cost saved |
|-------|-----------|---------------|-----|--------------|------------|
| **L1 — Query cache** | `sha256(canonical_query + category + filters)` | retrieval results (chunk IDs + scores) | 24h (72h for `search`-only) | corpus `document.versioned` event | rerank/retrieval cost, sub-second hits |
| **L2 — Context cache** | embedding hash + `doc_type` | chunk vectors | model-version lifetime | `embedding_model_version` change | embedding API calls (near-zero at this scale anyway) |
| **L3 — Brief cache** | `sha256(question + category + linked_docs)` | full generated brief | **24h** | `document.versioned`, `learning.created`, `outcome.recorded` | full premium pipeline (~$0.06) + 10–30s latency |

### 3.1 Same question = same answer?
**Yes with guardrails, not forever:**
- A cached brief is valid only if no *new precedent or learning* arrived since generation (index event invalidation covers this).
- Time-sensitive decisions (live negotiation, price changes) should bypass or shorten the brief cache — add a `time_sensitive` flag from the router's `urgency` field (brief cache TTL → 1h or off).
- Expected hit rates: repeated operational questions are common (~40–60% of Slack queries repeat within a week). Briefs repeat less (~20–30%) but save the most per hit.

**Hit-rate modeling** (see §6): at 40% query-cache hit, effective cost multiplier on query spend is 0.6×; brief-cache at 25% → 0.75× on premium spend.

---

## 4. Async vs Real-time

### 4.1 The split

| Mode | UX | Implementation | Compute profile |
|------|----|----------------|-----------------|
| **Real-time query** | Slack/web, p95 < 5s | cheap tier + retrieval + short generation | per-request, no batching |
| **Real-time brief** | Slack ack < 2s, full brief in thread ≤ 30s | ack → async premium job → reply | premium, per-request |
| **Scheduled reports** (nightly) | email 6:00, ≤ 60s runtime | batch job over new decisions/outcomes | **batched — shared context, cheaper, off-peak** |

### 4.2 Trade-off: speed vs compute cost
- **Batching wins by sharing context:** one nightly report over 10 new decisions can use *one* summarization pass over shared context instead of 10 separate premium calls → ~40–60% premium-token reduction on the report slice.
- **Real-time cannot batch** — that's the cost of the 5-second promise. Mitigate with tiering (cheap for answers) + caching (§3), so the only unbatchable premium spend is briefs (~5–20/day).
- **Latency floor is the LLM, not infra.** Don't over-invest in vector-DB latency to fix an LLM-bound path; invest in caching and async delivery instead.

### 4.3 Recommended posture
- All **answers**: real-time, cheap tier.
- All **briefs**: real-time-ack + async premium completion (matches MVP Week 3/4 design).
- **Reports + contradiction sweeps**: async nightly batch.

---

## 5. Monitoring & Cost Model

### 5.1 API-call volume estimate (per month)

Assumptions: org with ~30–60 active decision stakeholders.

| Item | Scenario A (pilot) | Scenario B (adopted) | Scenario C (scale) |
|------|--------------------|----------------------|--------------------|
| Questions (search/answers) | 500 | 5,000 | 20,000 |
| Decision briefs | 100 | 600 | 2,400 |
| Contradiction validations | 100 | 600 | 2,400 |
| Escalation checks | 100 | 600 | 2,400 |
| Ingest LLM (summarize/extract) | 150 | 900 | 3,600 |
| Embedding tokens/mo | ~0.5M | ~3M | ~12M |

### 5.2 Unit costs

| Unit | Tokens in/out | Cost/unit |
|------|---------------|-----------|
| Cheap call (router/escalation/answer) | ~200/100 | **~$0.001–0.002** |
| Premium brief (synthesize + risk + validate) | ~9,500 in / ~1,300 out | **~$0.05–0.06** |
| Embedding | 2M corpus, 500k/mo | **~$0.05 one-time / ~$0.01 mo** |
| Rerank (cross-encoder) | 40 items | ~$0.001–0.003 (or $0 if self-hosted) |

### 5.3 Monthly cost breakdown

| Line | A (pilot) | B (adopted) | C (scale) |
|------|-----------|-------------|-----------|
| Cheap LLM (answers + routing) | ~$1 | ~$10 | ~$40 |
| Premium LLM (briefs + validation) | ~$6 | ~$36 | ~$145 |
| Embeddings | ~$0.05 | ~$0.10 | ~$0.50 |
| **LLM subtotal** | **~$7** | **~$46** | **~$186** |
| Vector DB (pgvector on RDS) | $0–75 | $75–100 | $100–250 (or managed) |
| Infra (API/workers/web/Slack) | ~$0 (dev) | $100–150 | $200–400 |
| Observability/misc | ~$10 | $25 | $50 |
| **Total/month** | **~$20–90** | **~$250–320** | **~$540–900** |

**Key insight: LLM is < 25% of the bill even at scale.** The dominant costs are infrastructure and (real) engineering time — so optimize for correctness and adoption, not token-penny-pinching.

### 5.4 Monitoring & guardrails
| Metric | Alert | Threshold |
|--------|-------|-----------|
| Cost per brief | > $0.12 (2× expected) | drift investigation |
| Cost per query | > $0.01 (excluding briefs) | leak check (e.g., premium model used in cheap path) |
| Cache hit rate | < 25% on repeated questions | cache-key / dedupe bug |
| Brief p95 latency | > 30 s | async pipeline check |
| LLM error rate / retries | > 5% | provider or prompt issue |
| Embedding spend spike | re-embed loop detected | check model version migration |
| Budget ceiling per trace | enforced in orchestrator (spec §2.2) | hard stop |

---

## 6. Scaling Curves

### 6.1 Corpus size → cost
```
Tokens        Chunks(~300tok)  pgvector ok?   Embed cost (small)   Re-embed cost
──────        ────────────────  ────────────   ─────────────────   ─────────────
2M   (MVP)    ~7k               ✅ trivial      $0.04               $0.04
50M           ~165k             ✅ fine         $1.00               $1.00
100M          ~330k             ✅ fine         $2.00               $2.00
1B            ~3.3M             ⚠️ move to      $20.00              $20.00
                                 Qdrant/Weaviate
```
**Reading:** embedding cost is flat-negligible until ~1B tokens. The vector-DB move decision is driven by *latency + index size at 1M+ chunks*, not by embedding dollars.

### 6.2 Query volume → LLM cost (linear, cache-adjusted)
```
monthly_llm_cost ≈ (1 − h_q) · Q · c_q + (1 − h_b) · B · c_b + fixed
  Q = questions/mo   c_q ≈ $0.002        h_q = query-cache hit (→0.4)
  B = briefs/mo      c_b ≈ $0.06         h_b = brief-cache hit (→0.25)

Example (B, adopted): 0.6·5000·0.002 + 0.75·600·0.06 = $6 + $27 = $33/mo LLM
```

### 6.3 Engineering/ops cost dominates
- Each decision brief also consumes ~2–4 hours of *human* time today; that is 50–100× the LLM dollar cost of generating it. The ROI math below is where the system pays for itself.

---

## 7. ROI Calculation

### 7.1 Model
```
monthly_value = decisions_per_month × hours_saved_per_decision × loaded_hourly_rate
net_roi = monthly_value − (LLM + infra + amortized build cost)
```

### 7.2 Assumptions
| Variable | Conservative | Realistic | Aggressive |
|----------|--------------|-----------|------------|
| Decisions/month org-wide | 10 | 30 | 60 |
| Hours saved per decision | 1.5 | 3 | 4.5 |
| Loaded cost/hour | $80 | $120 | $180 |

### 7.3 Monthly value

| | Conservative | Realistic | Aggressive |
|--|--------------|-----------|------------|
| Value/month | $1,200 | **$10,800** | $48,600 |
| LLM+infra cost | ~$100 | ~$300 | ~$900 |
| **Net/month** | **~$1,100** | **~$10,500** | **~$47,700** |
| **Annual net** | **~$13k** | **~$126k** | **~$570k** |

**Break-even:** at realistic adoption, the MVP pays for itself in the first month of full use; even conservative usage covers infra + LLM costs ~11× over.

### 7.4 Unmodeled (soft) ROI
- **Decision speed:** weeks → days (faster supplier negotiations, launches).
- **Risk reduction:** avoiding repeated failures (a single avoided bad vendor contract ≈ many months of LLM spend).
- **Consistency + auditability:** institutional memory survives churn; every decision is traceable.

---

## 8. Optimization Recommendations (ranked by ROI)

| # | Recommendation | Impact | Effort |
|---|----------------|--------|--------|
| 1 | **Model tiering** (cheap router/answers, premium briefs) | 80% of theoretical token waste eliminated | Low |
| 2 | **Query cache** (L1, 24h TTL, index-event invalidation) | 0.6× on answer spend; sub-second repeats | Low |
| 3 | **Brief cache with invalidation** (L3, 24h, event-driven) | 0.75× premium spend; UX win | Low–Med |
| 4 | **Async briefs + nightly batch reports** | latency decoupled; 40–60% token savings on reports | Med |
| 5 | **Structured output / function-calling** | kills retry waste + schema failures | Low |
| 6 | **Prompt compression** (top-12 chunks, shared-context batching) | reduces premium input tokens per brief | Low |
| 7 | **Skip reranker in MVP** (add cross-encoder only if nDCG slips) | saves ~$0.001–0.003/query + latency | None |
| 8 | **Stay on hosted embeddings** until residency forces self-host | avoids $150–300/mo GPU for $0.04/mo of savings | None |
| 9 | **Budget guardrails** (per-trace cap, cost-per-brief alert) | prevents runaway spend | Low |
| 10 | **Adoption flywheel** (Slack-first, demos, outcome capture) | the biggest real lever — ROI is adoption-bound | High |

---

## 9. Open Questions
1. Confirm expected decision volume (per month) and loaded cost/hour — these dominate the ROI table.
2. Does legal/privileged content require self-hosted embeddings (BGE-M3) from Phase 1, or can it wait until confidential sources are ingested?
3. Is a 5-second inline brief ever required, or is ack-then-thread acceptable for all Slack briefs?
4. Should the nightly report be a PDF/email digest or an in-dashboard "intelligence inbox" first?
