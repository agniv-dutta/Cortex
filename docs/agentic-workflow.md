# Think9 Decision Intelligence — Agentic Workflow Design

**Version:** 1.0
**Status:** Draft for review
**Companion docs:** `decision-intelligence-spec.md` (full architecture), `decision-intelligence-mvp.md` (Phase-1 scope). This doc specifies the multi-agent orchestration for decision brief generation.

---

## 1. Workflow Overview

Four specialized agents cooperate to turn a user question into a validated decision brief:

```
 USER QUESTION
      │
      ▼
 ┌──────────────┐
 │  A1 QUERY    │  categorize + entities + brands + functions + confidence
 │  ROUTER      │
 └──────┬───────┘
        │ QueryContext
        ▼
 ┌──────────────┐
 │  A2 CONTEXT  │  top-5 decisions + similar negotiations + playbook sections
 │  RETRIEVER   │  hybrid ranking (relevance + recency + category match)
 └──────┬───────┘
        │ RetrievedContext
        ▼
 ┌──────────────┐
 │  A3 DECISION │  brief: recommended action + confidence, 3 precedents,
 │  SYNTHESIZER │  risks (legal/financial/supply/brand), alternatives, next steps
 └──────┬───────┘
        │ DraftBrief
        ▼
 ┌──────────────┐
 │  A4 VALIDATION AGENT │  contradiction flags + missing-context + confidence check
 └──────┬───────┘
        │ Verdict: PASS │ needs_revision │ escalate
        ▼
  Brief + flags + human-review routing
```

### Orchestration model (recommended)
**Deterministic DAG coordinator** (a small state machine, not an LLM driving the flow).

- Pros: reproducible, testable, auditable; agents are pure functions over typed inputs.
- Each agent is *exactly one LLM call* (or retrieval call) with a strict JSON schema — no unbounded tool loops inside an agent.
- The only controlled loop is the **Validation → Synthesis revision loop** (§5), bounded by `MAX_REVISION_ROUNDS = 2`.

LLM-driven tool-calling (agent calling agents) is explicitly **not** used in v1: it sacrifices traceability and makes fallback/escalation nondeterministic.

---

## 2. Inter-Agent Communication Format

### 2.1 Design principles
1. **Envelope + stage payloads.** One `WorkflowContext` envelope is passed agent-to-agent; each agent reads its input schema, writes its output schema, and appends provenance. No agent mutates another's payload.
2. **Strict typed contracts.** Every payload is a versioned JSON Schema. Validated server-side before hand-off (fail-closed on violation).
3. **Append-only provenance.** Each agent stamps `provenance[]` with `{agent, model, prompt_version, elapsed_ms, tokens, decision_id}`. The envelope is the audit record.
4. **Idempotent retries.** Envelope carries `attempt` counters; replaying an agent call with the same envelope + attempt number is safe.

### 2.2 The envelope

```jsonc
// WorkflowContext — shared across all agent handoffs
{
  "schema_version": "1.0",
  "trace_id": "trc_01JZ8X…",            // one trace per user request
  "decision_id": "dec_01JZ8…",          // null for ad-hoc questions
  "input": {
    "question": "Should we negotiate with Vendor X?",
    "channel": "slack",                 // slack | web | api
    "user_id": "U123",
    "session_id": "thr_abc",            // Slack thread / dashboard session
    "attachments": []                   // optional linked doc refs
  },
  "stage": {                            // which agent produced the last write
    "name": "A2_retriever",             // A1_router|A2_retriever|A3_synthesizer|A4_validator
    "attempt": 1,
    "status": "ok"                      // ok | degraded | failed | escalated
  },

  "payload": {
    "query_context": null,              // A1 output (§2.3)
    "retrieved_context": null,          // A2 output (§2.4)
    "draft_brief": null,                // A3 output (§2.5)
    "validation": null                  // A4 output (§2.6)
  },

  "control": {
    "revision_round": 0,                // increments on validate→synthesize loop
    "max_revision_rounds": 2,
    "cost_budget_usd": 1.00,            // hard ceiling per trace
    "token_budget": 8000,
    "timeout_s": 90,
    "escalation_level": 0               // 0=none,1=requester,2=SME,3=approval gate
  },

  "provenance": [                       // appended by every agent
    { "agent": "A1_router", "model": "gpt-4o-mini", "prompt_version": "router_v2",
      "elapsed_ms": 412, "tokens": { "in": 180, "out": 90 },
      "attempt": 1, "status": "ok" }
  ]
}
```

### 2.3 A1 → A2 payload: `query_context`

```jsonc
{
  "category": "procurement",            // procurement|brand|product|hr|legal|ops
  "category_confidence": 0.94,
  "category_evidence": "…",             // one-line model justification
  "entities": [
    { "type": "vendor", "name": "Vendor X",
      "canonical_id": "ven_01", "confidence": 0.98 },
    { "type": "brand", "name": "cortex", "confidence": 0.9 }
  ],
  "brands": ["cortex"],                 // ["all"] when brand-agnostic
  "functions": ["supply_chain", "finance"],
  "intent": "decision_brief",           // decision_brief | answer | precedent_search
  "retrieval_directives": {
    "required_types": ["decision", "playbook"],
    "preferred_recency_days": 540,      // recency bias for this query
    "min_precedent_outcomes": true      // prefer decisions with known outcome
  },
  "clarifying_question": null           // set when router asks user (§4.1)
}
```

### 2.4 A2 → A3 payload: `retrieved_context`

```jsonc
{
  "retrieval_summary": {
    "candidates_considered": 47,
    "reranked_top": 18,
    "evidence_coverage": { "decision": 0.8, "playbook": 0.6, "negotiation": 0.4 },
    "min_relevance": 0.62,              // lowest kept score
    "mode": "hybrid",                   // hybrid|dense|sparse|degraded
    "note": null                        // degradation reason, if any
  },
  "historical_decisions": [             // top-5
    { "decision_id": "dec_01…", "title": "Vendor X 2024 renewal",
      "category": "procurement", "brands": ["cortex"],
      "outcome": "success", "outcome_summary": "+6% discount",
      "date": "2024-11-02",
      "relevance": 0.88, "recency_bias": 0.9,
      "hybrid_score": 0.87, "match_reason": "same vendor, same category, prior negotiation",
      "chunk_refs": ["chunk_…"] }
  ],
  "similar_negotiations": [             // same-category or same-vendor, other vendors
    { "decision_id": "dec_02…", "title": "Northwind walk-away",
      "match_reason": "similar pricing dispute", "outcome": "failure",
      "relevance": 0.81, "chunk_refs": ["chunk_…"] }
  ],
  "playbook_sections": [
    { "document_id": "doc_…", "section": "§4 Negotiation timing rule",
      "chunk_id": "chunk_…", "relevance": 0.79,
      "applies_because": "renegotiation timing before contract expiry" }
  ],
  "evidence_gaps": [
    { "type": "missing_outcome", "description": "No outcome recorded for 2023 Vendor X renewal" }
  ]
}
```

### 2.5 A3 → A4 payload: `draft_brief`

```jsonc
{
  "recommended_action": {
    "action": "Open renegotiation with Vendor X now…",
    "confidence": 0.72,                 // 0–1
    "rationale": "2 of 3 comparable renewals improved terms with earlier starts",
    "evidence_notes": "based on 3 precedents; 1 outcome unknown"
  },
  "precedents": [                       // exactly 3, each with why/how it applies
    { "decision_id": "dec_01…", "title": "Vendor X 2024 renewal",
      "why_applies": "same vendor, same category, same quarter cadence",
      "how_applies": "start 2+ quarters out to gain discount leverage",
      "outcome": "success", "relevance": 0.88 },
    { "decision_id": "dec_02…", "title": "Northwind walk-away",
      "why_applies": "similar pricing dispute",
      "how_applies": "walk-away threat produced a better counteroffer",
      "outcome": "failure", "relevance": 0.81 },
    { "document_id": "doc_…", "chunk_id": "chunk_…",
      "title": "Playbook §4 negotiation timing", "why_applies": "governing rule",
      "how_applies": "do not renegotiate within 90 days of expiry", "relevance": 0.79 }
  ],
  "risk_factors": [
    { "type": "legal",  "severity": "high",   "likelihood": "medium",
      "risk": "Lock-in clause triggers on early renegotiation",
      "mitigation": "Exclude lock-in from scope", "source_chunk": "chunk_…" },
    { "type": "financial", "severity": "medium", "likelihood": "low",
      "risk": "Early prepayment penalty ~$120k", "mitigation": "Offset via discount", "source_chunk": "chunk_…" },
    { "type": "supply", "severity": "low", "likelihood": "low",
      "risk": "Vendor may delay feature support", "mitigation": "Contract SLA clause", "source_chunk": "chunk_…" },
    { "type": "brand", "severity": "low", "likelihood": "low",
      "risk": "Public dispute may leak to press", "mitigation": "NDA reaffirm", "source_chunk": "chunk_…" }
  ],
  "alternatives_considered": [
    { "action": "Wait until Q4", "tradeoff": "accepts 8% hike; avoids early termination risk" },
    { "action": "Multi-year extension", "tradeoff": "locks price, reduces flexibility" }
  ],
  "next_steps": {
    "approval_flow": { "gates": ["legal", "procurement"], "sla_hours": 24 },
    "owner": "supply_chain_lead",
    "suggested_tasks": ["Prepare BATNA sheet", "Schedule legal review"]
  },
  "provenance_chunks": ["chunk_…", "chunk_…", "chunk_…"]
}
```

### 2.6 A4 → orchestrator payload: `validation`

```jsonc
{
  "verdict": "needs_revision",          // pass | needs_revision | escalate
  "contradiction_flags": [
    { "flag_type": "contradicts", "severity": "high",
      "past_learning_ref": "memo_2026_q2_vendor_strategy",
      "quote": "…do not renegotiate contracts signed in current fiscal…",
      "conflict_reason": "recommended action violates standing Q2 strategy",
      "citation": "chunk_…" }
  ],
  "missing_context_alerts": [
    { "type": "outcome_unknown", "detail": "2023 Vendor X outcome not in corpus",
      "severity": "low" }
  ],
  "confidence_checks": {
    "evidence_density": 0.78,           // cited chunk overlap vs context
    "citation_validity": 1.0,           // fraction of citations resolving to real chunks
    "confidence_rating": "adequate"     // adequate | low | inflated
  },
  "revision_instructions": [            // set when verdict = needs_revision
    "Re-answer under the standing Q2 vendor strategy constraint and list the tradeoff explicitly.",
    "Lower recommendation confidence to ≤0.5 if evidence density <0.6."
  ],
  "escalation_reasons": []              // set when verdict = escalate (§6)
}
```

---

## 3. Agent Specifications

### 3.1 Agent 1 — Query Router
| Aspect | Spec |
|--------|------|
| Input | User question + channel + session |
| Output | `query_context` (§2.3) |
| Model | Cheap/fast (`gpt-4o-mini`); rule fallback (§4.1) |
| Skills | Category classification, entity extraction, brand/function tagging, intent detection |
| Fail-closed | If `category_confidence < 0.6` after fallback → emit `clarifying_question` and pause |

### 3.2 Agent 2 — Context Retriever
| Aspect | Spec |
|--------|------|
| Input | `query_context` |
| Output | `retrieved_context` (§2.4) |
| Model | Deterministic (no LLM). Dense + sparse hybrid; optional cheap LLM for `match_reason` synthesis |
| Ranking | `hybrid_score = w1·semantic + w2·category_match + w3·recency` — see §3.5 |
| Guarantee | Top-5 decisions + up to 5 similar negotiations + up to 5 playbook sections, each with `chunk_refs` |

### 3.3 Agent 3 — Decision Synthesizer
| Aspect | Spec |
|--------|------|
| Input | `retrieved_context` + `query_context` |
| Output | `draft_brief` (§2.5) |
| Model | Frontier reasoning model (`gpt-4o` / Claude Sonnet 4) |
| Constraints | Exactly 3 precedents; risk types must cover legal, financial, supply, brand; confidence 0–1 with written justification; no fabrication — unsupported claims go to `evidence_notes` |

### 3.4 Agent 4 — Validation Agent
| Aspect | Spec |
|--------|------|
| Input | `draft_brief` + re-fetched ground truth (learnings + decisions + standing memos) |
| Output | `validation` (§2.6) |
| Model | Frontier model in *checker* role; retrieval pass 2 against `learnings` collection |
| Checks | Contradiction vs standing strategy/learnings; citation validity; evidence density; confidence plausibility |
| Note | Validator sees the *raw chunks*, never A3's model memory — flags must cite ground truth |

### 3.5 Hybrid ranking formula (A2)
```
hybrid_score = 0.55 · semantic_cosine
             + 0.25 · category_match        (1 if same category, else 0.4)
             + 0.20 · recency_factor        (exp(-days_since / preferred_recency_days))
boost: +0.10 if outcome is known and relevant  (prefer decisions with outcomes)
penalty: -0.30 if document.status = 'archived' / 'superseded'
```
- Top-K per bucket: `K_decisions = 20, K_negotiations = 10, K_playbooks = 10` before final top-5/5/5 selection.
- Thresholds: keep items with `hybrid_score ≥ 0.5`; if fewer than 5 decisions clear it, fill with best-effort and mark in `evidence_gaps`.

---

## 4. Fallback Logic

### 4.1 Agent 1 — Router fallbacks
1. **Low category confidence (< 0.6):** run rule-based fallback (keyword + regex over query, term lists per category). If rule score ≥ 0.7 → use it, tag `status: degraded`, note in provenance.
2. **Rule fallback also weak:** switch to **clarify mode** — emit `clarifying_question` (e.g., "Is this about a specific vendor? Which brand?"), pause pipeline, resume on user reply (thread/session preserved). Max 1 clarify round.
3. **Entity extraction failure:** proceed with brand=`all`, functions=`unknown`; retrieves broad; `evidence_gaps` will surface the spread.

### 4.2 Agent 2 — Retriever fallbacks
| Condition | Fallback | Mode tag |
|-----------|----------|----------|
| Dense returns < 3 candidates | Retry with sparse/FTS only | `sparse` |
| Both dense+sparse empty | Drop category filter, expand brands to `all`, relax recency window 2× | `degraded` |
| Still < 3 candidates | Return empty `retrieved_context` with `evidence_gaps`; **do not synthesize** | `empty` |
| Vector store unavailable | Serve from FTS index only; degrade flag; alert on-call if >5min | `degraded` |

### 4.3 Agent 3 — Synthesizer fallbacks
1. **Structured-output validation fails:** re-prompt once with schema + original context (`attempt` 2), else fail-closed → no brief, escalate to requester.
2. **Insufficient evidence** (`retrieved_context.mode = empty` or `evidence_coverage < 0.3`): emit **evidence-gap response** instead of a brief — list what would be needed, offer to search more broadly. Never fabricate.
3. **Cost/time budget exceeded:** trim context to highest-scored 60% and regenerate once; if still over, escalate (§6) rather than silently truncate reasoning.

### 4.4 Agent 4 — Validator fallbacks
1. **Ground-truth re-fetch fails:** validations requiring `learnings` are skipped, brief passes with `confidence_rating: low` and a `missing_context` alert — a human review trigger fires (§6 R2).
2. **Validator LLM fails/structured output invalid:** treat as **fail-closed → escalate**, do not auto-pass.

---

## 5. The Validation → Revision Loop

```
        ┌──────────────────────────────┐
        │        A3 Synthesizer        │
        └──────────────┬───────────────┘
                       │ draft_brief
                       ▼
        ┌──────────────────────────────┐
        │        A4 Validation         │
        └──────────────┬───────────────┘
                       │ verdict
              ┌────────┼─────────┬──────────────┐
              ▼        ▼         ▼              ▼
            pass   needs_     escalate       insufficient
                   revision   (§6)          evidence
              │        │                        │
              │        ▼                        ▼
              │   revision_round ≥ 2 ?      evidence-gap
              │    ┌─────┴─────┐             response
              │    ▼           ▼
              │  no (loop)    yes
              │   │           │
              │   │           ▼
              │   │         escalate (§6 R1)
              ▼   ▼
         FINAL BRIEF + flags + routing
```

**Rules:**
- On `needs_revision`, A3 receives `revision_instructions` verbatim and regenerates only the affected sections (not the whole brief, to preserve grounding).
- `revision_round` increments per cycle; `max = 2`. Exceeding → **escalate** (R1).
- A revision must *tighten* the brief: if round 2 output is not materially different (edit distance / flag parity check), escalate instead of looping again.
- Every loop iteration is audited; the envelope retains each revision's `draft_brief` snapshot.

---

## 6. Escalation Rules

Escalation is a monotonic ladder. `escalation_level` 0→3 persists on the envelope and any higher-level output includes the lower-level history.

| Level | Trigger | Action |
|-------|---------|--------|
| **0 — None** | Validator `pass`, no flags | Auto-release brief to requester |
| **1 — Requester review** | High-severity contradiction flag; `confidence_rating: low`; category change between router and validator | Brief delivered with flags + explicit "review required"; requester must click-through |
| **2 — SME / function lead** | Revisions exhausted (R1); standing-memo contradiction of any severity (R2); evidence density < 0.4 with high-stakes category (procurement/legal) | Route to category owner (e.g., Head of Procurement); 24h SLA |
| **3 — Approval gate** | Risk severity high in legal or financial with no mitigation; cross-functional impact flagged; requester overrides SME | Standard approval-flow routing (§8 of full spec): e.g., Legal → Procurement → CFO |

**Mandatory escalation reasons (R-codes, surfaced in `escalation_reasons`):**
- **R1** — `needs_revision` repeated to `max_revision_rounds`.
- **R2** — Validator ground-truth unavailable (learnings fetch failed); cannot certify contradiction-free.
- **R3** — Recommendation contradicts a *standing/active* memo or playbook (any severity).
- **R4** — Evidence coverage below 0.3 for procurement, legal, or brand-critical categories.
- **R5** — Cost/token/time budget exceeded (prevents silent quality loss).
- **R6** — Category routing conflict (router said `procurement`, validator/retrieval strongly indicates `legal`).

**Escalation mechanics:** event `decision.escalated` on the event bus → notification to the target role → deadline timer starts → SLA breach auto-forwards to next level + manager. Every escalation includes the full envelope (trace + provenance) for fast review.

---

## 7. Human Review Triggers

Human review is *routed, not optional*, when any trigger below fires. Triggers are computed from validator output + envelope control state — never from model self-reporting alone.

| ID | Trigger | Condition | Reviewer | SLA | Result options |
|----|---------|-----------|----------|-----|----------------|
| H1 | High-severity contradiction | `flags.severity == high` (any type) | Requester + category SME | 24h | Accept w/ rationale (logged as future learning) · Request changes · Reject |
| H2 | Standing-memo conflict | R3 fired | Category SME | 24h | Override w/ executive sign-off · Block |
| H3 | Low confidence brief | `recommended_action.confidence < 0.5` and evidence density < 0.6 | Requester | 8h | Accept-as-informational · Deep-dive search · Reject |
| H4 | Insufficient evidence | Retrieval `empty`/`degraded`, or coverage < 0.3 in high-stakes category | Category SME | 48h | Approve data-gap task · Reject |
| H5 | Revision loop exhausted | R1 fired | Category SME | 24h | Approve as-is w/ notes · Hand to analyst to fix context |
| H6 | Category conflict | R6 fired | Cross-category SME pair | 24h | Assign authoritative category, re-run once |
| H7 | Execution-critical risk | legal or financial risk = high, no mitigation present | Legal or CFO gate | 48h | Approval gate (§8 full spec) · Reject |
| H8 | New/unknown subject | Router `category_confidence < 0.6` after clarify + broad retrieval returned no strong match | Designated triage owner | 48h | Log as training sample · Route manually |

**After review:** every human decision is written back to the learning loop — accepted contradictions become `learnings`, rejected briefs become negative training data, category fixes enrich router few-shot examples. This closes the "human review" into "system improvement" (§11 of the full spec).

---

## 8. Observability & Audit

- **Per-trace telemetry:** every agent emits an event (`agent.started`, `agent.completed`, `agent.failed`, `agent.escalated`) keyed by `trace_id` — enables the distributed trace view on the dashboard.
- **Audit record:** the full `WorkflowContext` envelope is persisted per trace (immutable); any brief can be replayed from envelope.
- **Metrics:** pipeline success rate by agent, revision-loop rate, escalation rate by reason code, human review SLA compliance, contradiction precision (human accept vs. ignore), mean brief confidence vs. post-hoc outcome.
- **Log levels:** debug (envelope payloads) available only with admin role; default log = events + provenance stamps only.

---

## 9. Phase Fit (MVP vs Full)

| Capability | MVP (Phase 1) | Full |
|------------|---------------|------|
| DAG orchestrator + envelope | ✅ | ✅ |
| A1 Router (category/brands/functions) | ✅ | ✅ |
| A2 Retriever (hybrid ranking) | ✅ | ✅ |
| A3 Synthesizer (brief) | ✅ | ✅ |
| A4 Validator (contradictions) | ✅ — learns from `decisions` + `learnings` seed set | ✅ — full learnings corpus |
| Clarify-mode fallback | ✅ | ✅ |
| Revision loop (max 2) | ✅ | ✅ |
| Escalation ladder (0–3) | Levels 0–1 automated; 2–3 = notify owner | Full gate routing |
| LLM-driven agent-to-agent calling | ❌ | Evaluate in Phase 4 |

---

## 10. Open Questions

1. Who owns the "standing strategy memos" (e.g., Q2 vendor strategy) — are they part of the `learnings` collection or a separate `memos` source in Phase 1?
2. Should H3 (low-confidence briefs) auto-deliver to the requester or require a human to unblock before sending?
3. Is a per-trace cost ceiling of $1.00 right for frontier-model briefs, or should it scale with decision class?
4. Do we need a "replay from envelope" audit tool in Phase 1 (nice-to-have vs. must-have for legal)?
