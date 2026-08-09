"""Meta-agent (docs/expert-agents.md §4) — synthesizes expert assessments + draft
brief into the unified decision brief.

The conflict-resolution logic is a deterministic, unit-testable core
(conflict_detection / resolution below); an optional premium-LLM pass rewrites the
unified-brief narrative and never runs if it would fail (no API key / error).
"""

import json
import logging
import re
from typing import Any

from app.core.envelope import ProvenanceStamp, StageName, WorkflowContext
from app.prompts.experts import META_PROMPT_VERSION, META_SYSTEM, meta_user
from app.schemas.brief import DraftBrief
from app.schemas.expert import (
    Conflict,
    ExpertAssessment,
    MetaEscalation,
    MetaSynthesis,
)
from app.services.jsonutil import parse_json_object

logger = logging.getLogger(__name__)

NEGATION_WORDS = {"no", "never", "without", "prohibit", "forbid", "not", "cannot", "disallow"}
AFFIRMATIVE_WORDS = {"require", "must", "need", "above", "increase", "exceed", "accept", "agree", "approve"}
STOPWORDS = {
    "and", "the", "with", "for", "from", "that", "this", "than", "into", "over", "under",
    "should", "will", "shall", "have", "has", "been", "are", "was", "being", "per", "each",
}
CONFIDENCE_FLOOR = 0.20
VETO_PENALTY = 0.15
HARD_CONSTRAINT_PENALTY = 0.10
SOFT_CONSTRAINT_PENALTY = 0.05
UNANIMOUS_BONUS = 0.05

SEVERITY_MAX = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}
SEVERITY_NAME = {v: k for k, v in SEVERITY_MAX.items()}


def _tokens(text: str) -> set[str]:
    words = {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in STOPWORDS}
    return {w for w in words if w not in NEGATION_WORDS and w not in AFFIRMATIVE_WORDS}


def hard_constraints_conflict(a: str, b: str) -> bool:
    """Heuristic: two hard constraints conflict when they share a significant subject
    token and one is negative while the other is affirmative."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta & tb:
        return False
    na = any(w in NEGATION_WORDS for w in re.findall(r"[a-z]+", a.lower()))
    nb = any(w in NEGATION_WORDS for w in re.findall(r"[a-z]+", b.lower()))
    aa = any(w in AFFIRMATIVE_WORDS for w in re.findall(r"[a-z]+", a.lower()))
    ab = any(w in AFFIRMATIVE_WORDS for w in re.findall(r"[a-z]+", b.lower()))
    return (na and ab) or (nb and aa)


def detect_conflicts(assessments: list[ExpertAssessment]) -> list[Conflict]:
    conflicts: list[Conflict] = []
    opposing = [a for a in assessments if a.verdict == "oppose"]
    non_opposing = [a for a in assessments if a.verdict != "oppose"]
    if len(assessments) >= 2 and opposing and non_opposing:
        conflicts.append(
            Conflict(
                between=[a.agent for a in opposing] + [a.agent for a in non_opposing],
                type="verdict",
                detail="oppose vs support/conditional split in the panel",
                resolved=False,
            )
        )
    hard = [
        (a.agent, c.constraint) for a in assessments for c in a.constraints if c.type == "hard"
    ]
    for i in range(len(hard)):
        for j in range(i + 1, len(hard)):
            ai, ci = hard[i]
            aj, cj = hard[j]
            if hard_constraints_conflict(ci, cj):
                conflicts.append(
                    Conflict(
                        between=[ai, aj],
                        type="hard_constraint",
                        detail=f"mutually exclusive hard constraints: '{ci}' vs '{cj}'",
                        resolved=False,
                    )
                )
    return conflicts


def merge_risks(assessments: list[ExpertAssessment]) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for a in assessments:
        for r in a.risks:
            key = a.agent
            current = merged.get(key, {"risk": "", "severity": "none", "source": ""})
            if SEVERITY_MAX.get(r.severity, 0) > SEVERITY_MAX.get(current["severity"], 0):
                merged[key] = {"risk": r.risk, "severity": r.severity, "source": r.evidence}
    return merged


def resolve(
    brief: DraftBrief,
    assessments: list[ExpertAssessment],
) -> tuple[MetaSynthesis, list[Conflict]]:
    """Deterministic conflict resolution + synthesis. Returns (meta, conflicts)."""
    conflicts = detect_conflicts(assessments)
    opposing = [a for a in assessments if a.verdict == "oppose"]
    escalating_agents = [a for a in assessments if a.escalate.flag]
    hard_conflicts = [c for c in conflicts if c.type == "hard_constraint"]
    majority_oppose = len(opposing) > len(assessments) / 2 if assessments else False

    hard_constraints = [c.constraint for a in assessments for c in a.constraints if c.type == "hard"]
    soft_constraints = [c.constraint for a in assessments for c in a.constraints if c.type == "soft"]

    escalations: list[MetaEscalation] = [
        MetaEscalation(agent=a.agent, reason=a.escalate.reason, to=a.escalate.to or "executive")
        for a in escalating_agents
    ]

    unresolved: list[str] = []
    if hard_conflicts:
        for c in hard_conflicts:
            unresolved.append(f"hard-constraint conflict: {c.detail}")
        escalations.append(MetaEscalation(agent="meta", reason="unresolvable hard-constraint conflict", to="executive"))
    if majority_oppose:
        unresolved.append("majority of the panel opposes")
        escalations.append(MetaEscalation(agent="meta", reason="majority oppose", to="executive"))

    # conflict resolution bookkeeping (C1/C4: veto with majority support → condition)
    vetoes = [a.agent for a in opposing]
    for c in conflicts:
        if c.type == "verdict":
            c.resolved = not majority_oppose
            c.resolution = (
                "escalated for executive review" if majority_oppose
                else "recommendation conditioned on vetoing agents' constraints"
            )

    # final status (priority: escalate > majority oppose > conditionally_approve > approve)
    if escalations:
        final_status = "escalate"
    elif majority_oppose:
        final_status = "escalate"
    elif vetoes or hard_constraints or soft_constraints:
        final_status = "conditionally_approve"
    else:
        final_status = "approve"

    # final confidence
    confidence = float(brief.recommended_action.confidence)
    for _ in vetoes:
        confidence -= VETO_PENALTY
    if hard_constraints:
        confidence -= HARD_CONSTRAINT_PENALTY
    unresolved_soft = [c for a in assessments if a.verdict != "support" for c in a.constraints if c.type == "soft"]
    confidence -= SOFT_CONSTRAINT_PENALTY * len(unresolved_soft)
    if assessments and all(a.verdict == "support" for a in assessments):
        confidence += UNANIMOUS_BONUS
    confidence = max(CONFIDENCE_FLOOR, min(1.0, round(confidence, 2)))
    if confidence < CONFIDENCE_FLOOR + 0.001:
        final_status = "escalate"
        unresolved.append(f"final confidence below {CONFIDENCE_FLOOR}")

    agreement = round(
        sum(1 for a in assessments if a.verdict in {"support", "conditionally_support"}) / len(assessments),
        2,
    ) if assessments else 0.0

    unified_brief: dict[str, Any] = {
        "recommended_action": {
            "action": brief.recommended_action.action,
            "confidence": confidence,
            "rationale": _build_rationale(assessments, vetoes),
        },
        "risk_factors": merge_risks(assessments),
        "approval_conditions": hard_constraints + soft_constraints,
        "expert_summary": {a.agent: a.summary for a in assessments},
        "vetoes": vetoes,
        "final_status": final_status,
        "final_confidence": confidence,
    }

    meta = MetaSynthesis(
        unified_brief=unified_brief,
        agreement=agreement,
        conflicts=conflicts,
        escalations=escalations,
        final_confidence=confidence,
        final_status=final_status,
        unresolved_conflicts=unresolved,
    )
    return meta, conflicts


def _build_rationale(assessments: list[ExpertAssessment], vetoes: list[str]) -> str:
    if not assessments:
        return "No expert panel ran."
    parts = []
    supports = [a.agent for a in assessments if a.verdict == "support"]
    conditionals = [a.agent for a in assessments if a.verdict == "conditionally_support"]
    if supports:
        parts.append(f"supported by {', '.join(supports)}")
    if conditionals:
        parts.append(f"conditionally supported by {', '.join(conditionals)}")
    if vetoes:
        parts.append(f"vetoed by {', '.join(vetoes)} (conditions required)")
    return "; ".join(parts) if parts else "assessment did not produce a clear signal."


class MetaAgent:
    def synthesize(
        self,
        envelope: WorkflowContext,
        brief: DraftBrief,
        assessments: list[ExpertAssessment],
        category: str,
        refine: bool = True,
    ) -> tuple[MetaSynthesis, ProvenanceStamp]:
        stamp = ProvenanceStamp(agent=StageName.E2_META.value, model="", prompt_version=META_PROMPT_VERSION)
        meta, _ = resolve(brief, assessments)

        if refine and assessments:
            try:
                from app.core.config import get_settings
                from app.providers.llm import get_llm

                llm = get_llm(get_settings().expert_llm_tier)
                stamp.model = llm.model
                raw = llm.complete(
                    META_SYSTEM,
                    meta_user(
                        brief_json=json.dumps(brief.model_dump()),
                        assessments_json=json.dumps([a.model_dump() for a in assessments]),
                        category=category,
                    ),
                    temperature=0.0,
                    max_tokens=1200,
                    json_mode=True,
                )
                data = parse_json_object(raw)
                ub = data.get("unified_brief") or {}
                if ub.get("recommended_action"):
                    meta.unified_brief["recommended_action"] = {
                        **meta.unified_brief["recommended_action"],
                        "action": ub["recommended_action"].get("action", meta.unified_brief["recommended_action"]["action"]),
                        "rationale": ub["recommended_action"].get("rationale", meta.unified_brief["recommended_action"]["rationale"]),
                    }
                meta.unified_brief["expert_summary"] = ub.get("expert_summary", meta.unified_brief["expert_summary"])
                meta.unified_brief["approval_conditions"] = ub.get("approval_conditions", meta.unified_brief["approval_conditions"])
                meta.note = "refined by meta LLM pass"
            except Exception as exc:  # deterministic fallback keeps the pipeline alive
                logger.info("meta LLM pass unavailable (%s); using rule-based synthesis", exc)
                meta.note = "rule-based synthesis (LLM refinement unavailable)"

        envelope.stamp(stamp)
        return meta, stamp
