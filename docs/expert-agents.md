# Expert Agents — Specialized Assessment Layer

Extends the A1→A4 pipeline (agentic-workflow.md) with a panel of domain expert agents
and a meta-agent that synthesizes their assessments into the unified decision brief.
The panel runs **between the A4 revision loop and escalation**, so validation output
feeds expert assessment and expert output feeds the escalation ladder.

## 1. The panel

Five specialized expert agents, each owning one domain:

| Agent | Domain | Evaluates | Escalation role |
|---|---|---|---|
| `legal` | Compliance & contract language | obligations, exclusivity, indemnity, liability, regulatory clauses, termination risk | `legal_counsel` |
| `financial` | Budget, cash flow, ROI | capex/opex impact, working capital, payback, budget headroom, fx/price exposure | `cfo` |
| `supply_chain` | Vendor & material risk | vendor reliability, lead-time risk, MOQ fit vs forecast, single-sourcing, buffers | `supply_chain_manager` |
| `brand` | Brand identity & positioning | voice/tone fit, consumer perception, competitive positioning, market alignment | `brand_lead` |
| `operations` | Feasibility & resources | capacity, staffing, timeline, dependencies, tooling, launch-readiness | `ops_head` |

### Routing (category → agents)

| A1 category | Agents |
|---|---|
| `procurement` | supply_chain, financial, legal, operations |
| `brand` | brand, operations, financial |
| `product` | financial, supply_chain, brand, operations |
| `hr` | operations, financial, legal |
| `legal` | legal, financial |
| `ops` | operations, supply_chain, financial |

`required_expertise` from A1 augments the map (e.g. `cfo`→financial, `legal_counsel`→legal).
The meta-agent always runs.

## 2. Agent prompts

Each agent uses the same **output schema** and a role-specific **system prompt**.
Prompts are versioned in `app/prompts/experts.py` (`PROMPT_VERSION`).

### Shared output schema (per assessment)

```jsonc
{
  "agent": "legal",
  "verdict": "support | conditionally_support | oppose",
  "summary": "one-paragraph assessment",
  "risks": [{"risk": str, "severity": "none|low|medium|high|critical",
             "likelihood": "low|medium|high", "impact": str,
             "evidence": str, "mitigation": str}],
  "opportunities": [{"opportunity": str, "value": str, "evidence": str}],
  "constraints": [{"constraint": str, "type": "hard|soft",
                   "reason": str, "owner": str}],
  "recommendation": str,
  "confidence": 0.0,
  "escalate": {"flag": false, "reason": str, "to": "legal_counsel"},
  "assumptions": [str]
}
```

**Verdict semantics** — every agent must pick exactly one:
- `support` — proceed as recommended.
- `conditionally_support` — proceed **only if** the listed constraints are met.
- `oppose` — recommend against as drafted (a **veto**).

**Constraint semantics**:
- `hard` — blocking; the recommendation must be adjusted or the decision escalates.
- `soft` — preferred; violation degrades confidence but does not block.

### System prompts (abridged)

- **Legal** — "Check the recommendation against compliance rules and contract language.
  Flag obligations, exclusivity/indemnity/liability clauses, regulatory exposure, termination
  and change-of-control risk. Verdict `oppose` only for a hard legal violation; otherwise
  `conditionally_support` with the clause changes required. Cite each risk to the provided
  contract/decision evidence."
- **Financial** — "Assess budget headroom, cash-flow and working-capital impact, ROI and
  payback, capex/opex split, and price/fx exposure. `oppose` when the decision exceeds a
  hard budget cap or has a negative NPV that cannot be recovered; otherwise require terms
  (payment schedule, hedging, break-even) as conditions."
- **Supply Chain** — "Assess vendor reliability (history, single-sourcing), lead-time risk,
  MOQ vs. forecast fit, minimum-buffer levels, and transportation exposure. `oppose` only
  when supply continuity is at stake with no mitigation; otherwise require buffer/MOQ
  adjustments as conditions."
- **Brand** — "Verify alignment with brand identity, voice, and market positioning; assess
  consumer-perception and competitive impact. `oppose` only when the decision materially
  contradicts positioning; otherwise condition on messaging/campaign guardrails."
- **Operations** — "Check feasibility: capacity, staffing, tooling, dependencies, and the
  timeline to execute. `oppose` when execution within the stated timeline is not feasible;
  otherwise condition on resource/staffing commitments."

Each user prompt is rendered from the same template:

```
<CONTEXT>            <- domain-filtered retrieved chunks for this agent
</CONTEXT>
DECISION STATEMENT, CATEGORY, BRANDS, URGENCY, KEY FACTS
RECOMMENDED ACTION  <- from the A3 brief
Return JSON per the schema.
```

## 3. Inter-agent communication protocol

The panel follows the same envelope discipline as A1–A4 (agentic-workflow.md §2):

- **No agent-to-agent messages.** Each expert reads only `payload.query_context`,
  `payload.retrieved_context` (domain-filtered) and `payload.draft_brief`; it writes only
  `payload.expert_assessments[agent]`. The meta-agent is the **sole aggregator** — it reads
  all assessments and writes `payload.meta_output`.
- Every call appends a `ProvenanceStamp` (`E1_expert_panel` / `E2_meta`) recording agent,
  model, prompt version, elapsed time, and tokens.
- Agents run **in parallel** (thread pool, `expert_parallelism`); assessments are
  immutable once produced, so ordering never affects output.
- If an agent's LLM call fails, a **degraded assessment** is emitted (verdict
  `conditionally_support`, confidence 0.3, `escalate.flag=true` with the failure reason).
  The panel never silently drops an agent — fail-safe means a broken agent escalates.

## 4. Meta-agent synthesis

`E2_meta` consumes the A3 brief + all expert assessments and produces the unified brief:

1. **Merge risks** — union across agents, keyed by type (legal/financial/supply_chain/brand/operations);
   severity per type = the maximum across agents.
2. **Collect constraints** — all hard + soft constraints become approval conditions; hard
   constraints are surfaced first in `approval_flow.gates`.
3. **Compute agreement** — fraction of agents with `support`/`conditionally_support`.
4. **Detect and resolve conflicts** (below).
5. **Adjust final confidence** and set the final status.
6. **Emit escalations** — union of agent escalation flags + meta-level unresolved conflicts.

### Conflict resolution logic

Conflicts are detected in priority order; the first applicable rule wins. A conflict is
either *resolved* (recommendation adjusted / conditions added) or *escalated* (human).

| # | Rule | Detection | Resolution |
|---|---|---|---|
| C1 | **Veto** | any `oppose` verdict | Not automatic rejection. Meta proposes condition adjustments to satisfy the vetoing agent's constraints. If the veto carries hard constraints and adjustments cannot satisfy them → escalate to that agent's role. |
| C2 | **Majority oppose** | >50% of panel `oppose` | Escalate; final status `escalate`; confidence floored. |
| C3 | **Hard-constraint conflict** | two hard constraints on the same subject token where one is negative (no/never/without/prohibit) and the other affirmative (require/must/increase/above) | Mutually exclusive → **unresolvable without human** → escalate. |
| C4 | **Verdict split (minority veto)** | ≥2 agents, mixed `oppose` vs `support`/`conditional`, majority support | `conditionally_approve` with the vetoing agent's constraints as conditions; confidence penalty. |
| C5 | **Agent escalation flag** | any `escalate.flag=true` | Escalate to the flag's `to` role (mapped to `legal_counsel`/`cfo`/`supply_chain_manager`/`brand_lead`/`ops_head`). |
| C6 | **Confidence floor** | final confidence < 0.2 | Escalate for sign-off. |

**Final confidence** (deterministic):

```
base = brief.recommended_action.confidence
- 0.15 per vetoing agent
- 0.05 per unresolved soft constraint
- 0.10 when hard constraints require recommendation adjustment
- 0.05 bonus when the panel is unanimous (all support)
floor = 0.20
```

**Final status** priority: `escalate` > `oppose` (majority) > `conditionally_approve` > `approve`.

A **rule-based fallback** always runs; an optional LLM pass (premium tier) rewrites the
unified-brief narrative. The fallback keeps the pipeline working and testable without API keys.

## 5. Escalation to humans

Escalations carry a reviewer role and a reason; they merge with the existing
`EscalationService` output (higher of the two — any escalation trigger escalates):

- Agent flags → mapped human role.
- C2/C3/C6 → `executive` / `category_lead`.
- Unresolved conflicts surface in `meta.unresolved_conflicts` and in the decision's flags.

The decision status becomes `pending_review` whenever the meta status is `escalate` or
any agent escalated.

## 6. Cost & latency

Each decision now performs ≤ `|panel|` extra premium calls (parallel) + 1 meta call.
Panel size by category: procurement/ops = 4, product = 4, brand = 3, hr = 3, legal = 2.
`expert_agents_enabled` toggles the whole layer; `expert_llm_tier` (default `premium`)
controls the tier. Parallel execution keeps added latency ≈ one premium round-trip.
