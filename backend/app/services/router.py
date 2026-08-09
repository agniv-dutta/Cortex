"""Agent 1 — Query Router (agentic-workflow.md §3.1).

Primary path: cheap-tier LLM classification. Fallback: rule-based keyword
classifier (agentic-workflow.md §4.1). If both are weak, emit a clarifying
question instead of guessing.
"""

import logging

from app.core.envelope import ProvenanceStamp, StageName, StageStatus, WorkflowContext
from app.prompts import PROMPT_VERSION, ROUTER_SYSTEM, router_user
from app.providers.llm import get_llm
from app.schemas.context import CATEGORIES, QueryContext
from app.services.jsonutil import parse_json_object

logger = logging.getLogger(__name__)

RULE_FALLBACK: dict[str, list[str]] = {
    "procurement": ["vendor", "supplier", "moq", "negotiat", "contract", "pricing", "purchase", "procure", "renewal"],
    "brand": ["brand", "campaign", "voice", "tone", "packaging", "sponsorship", "launch"],
    "product": ["product", "formulation", "skus", "skipp", "co-pack", "supply of", "launch date"],
    "hr": ["hiring", "hire", "compensation", "salary", "benefits", "retention", "reorg", "team"],
    "legal": ["legal", "lawsuit", "liability", "exclusivity", "indemn", "compliance", "clause"],
    "ops": ["supply disruption", "capacity", "fulfillment", "warehouse", "process", "ops", "logistics"],
}

ROUTER_PROMPT_VERSION = f"router_v{PROMPT_VERSION}"


def _rule_fallback(question: str) -> QueryContext:
    q = question.lower()
    best, best_score = "ops", 0
    for category, keywords in RULE_FALLBACK.items():
        score = sum(1 for kw in keywords if kw in q)
        if score > best_score:
            best, best_score = category, score
    return QueryContext(
        category=best,
        sub_category="",
        category_confidence=min(0.7, 0.3 + 0.1 * best_score),
        brands=["all"],
        functions=[],
        urgency="low",
        intent="decision_brief",
        category_evidence=f"rule-based fallback matched {best_score} keyword(s)",
    )


class QueryRouter:
    def __init__(self) -> None:
        self.llm = get_llm("cheap")

    def route(self, envelope: WorkflowContext, known_brands: str = "") -> tuple[QueryContext, ProvenanceStamp]:
        question = envelope.input.question
        channel = envelope.input.channel
        stamp = ProvenanceStamp(agent=StageName.A1_ROUTER.value, model=self.llm.model, prompt_version=ROUTER_PROMPT_VERSION)
        qc: QueryContext | None = None

        try:
            raw = self.llm.complete(
                ROUTER_SYSTEM,
                router_user(question, channel, known_brands),
                temperature=0.0,
                max_tokens=400,
                json_mode=True,
            )
            data = parse_json_object(raw)
            category = data.get("category")
            if category in CATEGORIES:
                qc = QueryContext(
                    category=category,
                    sub_category=str(data.get("sub_category", "")),
                    category_confidence=float(data.get("category_confidence", 0.0)),
                    category_evidence=str(data.get("category_evidence", "")),
                    brands=data.get("brands") or ["all"],
                    functions=data.get("functions") or [],
                    urgency=str(data.get("urgency", "low")),
                    required_expertise=data.get("required_expertise") or [],
                    key_facts=data.get("key_facts") or [],
                    intent="decision_brief",
                    clarifying_question=None,
                )
                vendor = (data.get("entities") or {}).get("vendor")
                if vendor:
                    qc.entities = [{"type": "vendor", "name": vendor, "confidence": 1.0}]
        except Exception as exc:  # pragma: no cover
            logger.warning("router LLM path failed (%s); using rule fallback", exc)
            stamp.status = StageStatus.DEGRADED.value

        if qc is None:
            qc = _rule_fallback(question)
            stamp.status = StageStatus.DEGRADED.value

        if qc.category_confidence < 0.6:
            fallback = _rule_fallback(question)
            if fallback.category_confidence >= 0.7:
                qc = fallback
                stamp.status = StageStatus.DEGRADED.value
            else:
                qc.clarifying_question = (
                    "I couldn't classify this confidently. Is this about a specific "
                    "vendor/supplier, brand, or product? Which function owns it?"
                )
                stamp.status = StageStatus.DEGRADED.value

        stamp.elapsed_ms = 0  # caller fills timing if desired
        return qc, stamp
