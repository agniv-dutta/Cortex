"""Escalation advisor (agentic-workflow.md §6, prompts.md §5).

Rule pre-checks first (critical/high contradiction, confidence < 0.4); LLM
decides reviewer set otherwise. Fail-safe: on any error, escalate.
"""

import json
import logging

from app.core.envelope import ProvenanceStamp
from app.prompts import ESCALATION_SYSTEM, PROMPT_VERSION, escalation_user
from app.providers.llm import LLMProvider, get_llm
from app.schemas.brief import ContradictionFlag, DraftBrief, EscalationDecision
from app.services.jsonutil import parse_json_object

logger = logging.getLogger(__name__)

ESCALATION_PROMPT_VERSION = f"escalation_v{PROMPT_VERSION}"

CONFIDENCE_FLOOR = 0.4
FINANCIAL_EXEC_CAP = 500_000


class EscalationService:
    def __init__(self) -> None:
        self.llm: LLMProvider = get_llm("cheap")

    def decide(
        self,
        brief: DraftBrief,
        flags: list[ContradictionFlag],
        category: str,
        impact_usd: str = "",
    ) -> tuple[EscalationDecision, ProvenanceStamp]:
        stamp = ProvenanceStamp(agent="escalation", model=self.llm.model, prompt_version=ESCALATION_PROMPT_VERSION)

        # rule pre-checks
        if any(f.severity == "critical" or (f.flag_type in {"contradicts", "repeats_failure"} and f.severity == "high") for f in flags):
            decision = EscalationDecision(
                escalate=True,
                reviewer=["cfo", "category_lead"],
                reason="high/critical contradiction flagged; executive review required.",
                conditions_to_defer="Override with written executive rationale.",
            )
            return decision, stamp
        if brief.recommended_action.confidence < CONFIDENCE_FLOOR:
            decision = EscalationDecision(
                escalate=True,
                reviewer=["cfo", "category_lead"],
                reason=f"confidence {brief.recommended_action.confidence:.2f} below {CONFIDENCE_FLOOR}; executive sign-off or documented deferral required.",
                conditions_to_defer="Raise confidence via outcome-confirmed precedent.",
            )
            return decision, stamp

        try:
            raw = self.llm.complete(
                ESCALATION_SYSTEM,
                escalation_user(
                    brief_json=json.dumps(brief.model_dump()),
                    category=category,
                    impact_usd=impact_usd,
                    flags_json=json.dumps([f.model_dump() for f in flags]),
                ),
                temperature=0.0,
                max_tokens=300,
                json_mode=True,
            )
            data = parse_json_object(raw)
            decision = EscalationDecision(
                escalate=bool(data.get("escalate", False)),
                reviewer=data.get("reviewer") or [],
                reason=str(data.get("reason", "")),
                conditions_to_defer=data.get("conditions_to_defer"),
            )
        except Exception as exc:  # pragma: no cover — fail-safe on the safe side
            logger.warning("escalation LLM failed (%s); fail-safe escalate", exc)
            decision = EscalationDecision(
                escalate=True, reviewer=["category_lead"], reason="escalation prompt failed; fail-safe escalation."
            )
        return decision, stamp
