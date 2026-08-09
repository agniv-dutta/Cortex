"""Fine-tuning dataset export (docs/feedback-loops.md §3.3).

Builds versioned JSONL training records from decisions with recorded outcomes so
the brief LLM can be fine-tuned on Think9-specific decision patterns. Success and
partial outcomes are positive examples; failures are tagged for preference-style
tuning.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.db.models import Decision, DecisionBrief, Outcome

EXCLUDE_RESULTS = {"superseded"}


def build_rows(session: Session) -> list[dict]:
    brief_by_decision: dict[str, DecisionBrief] = {}
    for b in session.query(DecisionBrief).order_by(DecisionBrief.created_at.desc()):
        brief_by_decision.setdefault(b.decision_id, b)

    rows: list[dict] = []
    for outcome in session.query(Outcome).all():
        if outcome.result in EXCLUDE_RESULTS:
            continue
        decision = session.get(Decision, outcome.decision_id)
        brief = brief_by_decision.get(outcome.decision_id)
        if decision is None or brief is None:
            continue
        brief_data = brief.brief or {}
        action = (brief_data.get("recommended_action") or {}).get("action", "")
        rationale = (brief_data.get("recommended_action") or {}).get("rationale", "")
        rows.append(
            {
                "instruction": f"Produce a decision brief for: {decision.statement}",
                "output": action and f"Recommended action: {action}." + (f" Rationale: {rationale}" if rationale else ""),
                "meta": {
                    "category": decision.category,
                    "decision_class": decision.decision_class,
                    "confidence": brief.confidence,
                    "outcome": outcome.result,
                    "metric_deltas": outcome.metric_deltas,
                },
            }
        )
    return rows


def export_filename() -> str:
    return f"finetune_think9_{date.today().isoformat()}.jsonl"
