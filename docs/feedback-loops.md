# Feedback Loops — Learning from Outcomes

Defines how Think9 records decisions and outcomes, measures itself, and improves
over time. Three tiers: **collect** (logging), **analyze** (metrics), **improve**
(retrained confidence, ranking boost, fine-tuning), plus **reporting**.

## 1. Outcome data collection

### Event types

| Event | Table | Trigger | Fields |
|---|---|---|---|
| Brief generated | `decision_briefs` | orchestrator | brief JSON, confidence, model_info, revision_round |
| Provenance used | `brief_chunks` | orchestrator | brief → chunk refs |
| Review / approval | `review_events` | human reviewer (`POST /v1/decisions/{id}/review`) | action `approved\|rejected\|deferred\|overridden`, reviewer, reason |
| Actual outcome | `outcomes` | human (`PUT /v1/decisions/{id}/outcome`) | result `success\|partial\|failure\|superseded`, metric_deltas, narrative |
| Learning statement | `learnings` | admin curation / automated (spec §11.3) | derived rules from outcomes |

Every decision gets a `review_due_at` when approved: **6 months later**, when an
outcome should be recorded (`success`/`partial`/`failure`). An `outcome_due` flag
powers a due-outcomes dashboard view.

### Outcome definitions

- `success` — the recommended action achieved its stated objective.
- `partial` — partially achieved (attach `metric_deltas`).
- `failure` — objective missed or actively harmful.
- `superseded` — decision replaced; excluded from accuracy scoring.

`metric_deltas` keys consumed by reporting: `savings_usd`, `cost_usd`,
`margin_delta_pct`, `timeline_days`. `narrative` is free text for learning extraction.

## 2. Metrics

| Metric | Definition | Source |
|---|---|---|
| **Decision accuracy** | `(success + 0.5·partial) / decisions_with_outcome` per category / decision_class / brand | `outcomes` × `decisions` |
| **Confidence calibration** | Per bucket (0.2–1.0, width 0.1): predicted mean vs observed success rate; **weighted calibration error** = Σ w·\|predicted − observed\| | briefs × outcomes |
| **Precedent usefulness** | Per precedent chunk: `accuracy = (success + 0.5·partial)/used`; **useful** = accuracy ≥ 0.7 and used ≥ 3 | `brief_chunks` × outcomes |
| **Blind spots** | Categories with failure rate ≥ 30% **or** outcome coverage < 40% **or** persistent evidence gaps | briefs (evidence_gaps) × outcomes |
| **Decision velocity** | decisions per month (created_at) — 3-month trend | `decisions` |
| **Cost savings** | Σ positive `metric_deltas.savings_usd`; cost leakage = Σ negative `cost_usd` | `outcomes` |
| **Adoption** | share of decisions with recorded outcome within 6 months of `review_due_at` | `decisions` × `outcomes` |

## 3. Continuous improvement

### 3.1 Retrained confidence scoring

`ConfidenceCalibrator` fits a **piecewise-linear recalibration map** from historical
`(predicted_confidence, outcome)` pairs (isotonic-style, monotone non-decreasing):

```
buckets of width 0.1 over [0.2, 1.0]
observed[b] = success_rate of decisions whose predicted confidence fell in bucket b
calibrated(c) = linear interpolation between bucket midpoints' observed rates
                (clamped to [0.2, 1.0]; under-sampled buckets → fall back to
                 the global success rate)
```

The fitted map is snapshotted to `calibration_models` (versioned, one active row).
`apply(confidence)` transforms any raw score at brief time (orchestrator) and at
retrieval time. **Cadence:** retrain when `≥ 50` new outcomes since the active
model, and at least monthly; trigger via `POST /v1/admin/calibration/retrain` or
the scheduled job.

### 3.2 Retrieval ranking adjustment

`PrecedentStat` (per chunk: `used_count`, `success_count`, `failure_count`,
`accuracy`) is rebuilt from `brief_chunks` × `decisions` × `outcomes`.

`PrecedentBoostProvider` turns those stats into a **ranking boost**: chunks whose
document is a `decision` and that are *proven accurate* get

```
boost = 0.15 · (accuracy − 0.6) / 0.4        # for accuracy ≥ 0.6 and used_count ≥ 3
```

added to `hybrid_score` (≤ 0.15). Historical decisions with confirmed-good
outcomes therefore surface above speculative matches. Chunks never penalized —
the boost is strictly non-negative (zero for unproven). **Cadence:** rebuilt on
every outcome recording plus nightly; ranking weights stay config-driven
(`precedent_boost_max`, `precedent_min_accuracy`, `precedent_min_uses`).

### 3.3 Fine-tuning dataset

`FinetuneExporter` emits versioned JSONL training records from decisions with
outcomes:

```jsonc
{"instruction": "produce a decision brief for: <statement>",
 "output": "<recommended action + rationale>",
 "meta": {"category": "...", "confidence": 0.8, "outcome": "success"}}
```

**Cadence:** monthly snapshot via `GET /v1/admin/finetune/export` (or script
`scripts/export_finetune.py`); the actual model fine-tune runs offline/CI with the
snapshot. Output rows with `success`/`partial` outcomes only (positive examples),
plus `failure` rows tagged as negative examples for preference-style tuning.

### Update cadence summary

| Model / data | Rebuild trigger | Interval |
|---|---|---|
| `PrecedentStat` | outcome recorded, manual `POST /v1/admin/ranking/rebuild` | nightly |
| `calibration_models` | `POST /v1/admin/calibration/retrain` | ≥50 new outcomes or monthly |
| Fine-tune dataset | `POST /v1/admin/finetune/export` | monthly |
| LLM fine-tune run | offline (CI/manual) from snapshot | monthly |

## 4. Reporting

**Dashboard** (`GET /v1/admin/dashboard`): decision velocity (monthly trend),
accuracy trend (rolling 3 months), cost savings YTD, top accurate categories,
active calibration error, precedent-use coverage.

**Monthly report** (`GET /v1/admin/report/monthly?month=YYYY-MM`):
- **Top decisions** — highest absolute `metric_deltas` impact, with outcome.
- **Emerging patterns** — category/decision_class with rising volume or rising
  accuracy; repeated failure themes (narrative keyword clusters).
- **Organizational blind spots** — categories with low outcome coverage, high
  failure rate, or persistent evidence gaps, each with a suggested next step.
- Accuracy summary + calibration trend.

**Admin analysis** (`GET /v1/admin/analysis`): the raw metric tables backing both
reports (accuracy by category, calibration buckets, precedent usefulness,
blind spots).

## 5. Guardrails

- Every metric uses **only decisions with recorded outcomes**; coverage is always
  reported alongside accuracy so small samples are not over-read.
- Calibration and precedent boosts apply **only above minimum sample counts**
  (`precedent_min_uses`, calibration bucket floor).
- Human override of any generated decision (reject/override) is stored in
  `review_events` and is itself an input to blind-spot analysis.
