"""Expert panel execution (docs/expert-agents.md §2–3).

Each agent receives a domain-filtered slice of the retrieved context plus the A3
recommended action, and emits one ExpertAssessment. Agents run in parallel via a
thread pool; a failed agent emits a degraded (fail-safe) assessment instead of
dropping from the panel.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from app.core.config import Settings, get_settings
from app.core.envelope import ProvenanceStamp, StageName, WorkflowContext
from app.prompts.experts import EXPERT_PROMPT_VERSION, EXPERT_SYSTEMS, expert_user
from app.providers.llm import LLMProvider, get_llm
from app.schemas.brief import DraftBrief
from app.schemas.context import RetrievedContext
from app.schemas.expert import EscalationFlag, ExpertAssessment
from app.services.experts.routing import domain_doc_types, panel_for
from app.services.jsonutil import parse_json_object
from app.services.synthesizer import build_context_pack

logger = logging.getLogger(__name__)


def _build_domain_context(agent: str, rc: RetrievedContext, settings: Settings) -> list[dict]:
    packed = build_context_pack(rc, settings.context_token_budget // 2)
    allowed = domain_doc_types(agent)
    domain = [p for p in packed if p["doc_type"] in allowed or p["kind"] in {"decision", "playbook"}]
    fallback = [p for p in packed if p not in domain]
    domain = (domain or fallback)[:6]
    return [
        {
            "citation": f"[{p['doc_id']}, {p['chunk_id']}, {p['doc_type']}]",
            "title": p["title"],
            "content": p["body"],
        }
        for p in domain
    ]


def _parse_assessment(agent: str, raw: str) -> ExpertAssessment:
    data = parse_json_object(raw)
    verdict = str(data.get("verdict", "conditionally_support"))
    if verdict not in {"support", "conditionally_support", "oppose"}:
        verdict = "conditionally_support"
    esc = data.get("escalate") or {}
    return ExpertAssessment(
        agent=agent,
        verdict=verdict,
        summary=str(data.get("summary", "")),
        risks=[
            {
                "risk": r.get("risk", ""),
                "severity": r.get("severity", "low"),
                "likelihood": r.get("likelihood", ""),
                "impact": r.get("impact", ""),
                "evidence": r.get("evidence", ""),
                "mitigation": r.get("mitigation", ""),
            }
            for r in (data.get("risks") or [])
        ],
        opportunities=[
            {
                "opportunity": o.get("opportunity", ""),
                "value": o.get("value", ""),
                "evidence": o.get("evidence", ""),
            }
            for o in (data.get("opportunities") or [])
        ],
        constraints=[
            {
                "constraint": c.get("constraint", ""),
                "type": "hard" if c.get("type") == "hard" else "soft",
                "reason": c.get("reason", ""),
                "owner": c.get("owner", ""),
            }
            for c in (data.get("constraints") or [])
        ],
        recommendation=str(data.get("recommendation", "")),
        confidence=float(data.get("confidence", 0.0)),
        escalate=EscalationFlag(
            flag=bool(esc.get("flag", False)),
            reason=str(esc.get("reason", "")),
            to=str(esc.get("to", "")),
        ),
        assumptions=[str(a) for a in (data.get("assumptions") or [])],
    )


def degraded_assessment(agent: str, reason: str) -> ExpertAssessment:
    return ExpertAssessment(
        agent=agent,
        verdict="conditionally_support",
        summary=f"Assessment unavailable: {reason}",
        recommendation="Flagged for human review — agent could not assess.",
        confidence=0.3,
        escalate=EscalationFlag(flag=True, reason=reason, to="executive"),
        status="degraded",
    )


class ExpertAgent:
    def __init__(self, llm: LLMProvider, settings: Settings | None = None) -> None:
        self.llm = llm
        self.settings = settings or get_settings()

    def assess(
        self,
        agent: str,
        envelope: WorkflowContext,
        qc,
        rc: RetrievedContext,
        brief: DraftBrief,
    ) -> tuple[ExpertAssessment, ProvenanceStamp]:
        stamp = ProvenanceStamp(
            agent=StageName.E1_EXPERT_PANEL.value,
            model=self.llm.model,
            prompt_version=EXPERT_PROMPT_VERSION,
        )
        try:
            domain = _build_domain_context(agent, rc, self.settings)
            user = expert_user(
                agent=agent,
                decision_statement=envelope.input.question,
                category=qc.category,
                brands=",".join(qc.brands),
                urgency=qc.urgency,
                key_facts=getattr(qc, "key_facts", []) or [],
                recommended_action=json.dumps(brief.recommended_action.model_dump()),
                context_json=json.dumps(domain),
            )
            raw = self.llm.complete(
                EXPERT_SYSTEMS[agent], user, temperature=0.0, max_tokens=900, json_mode=True
            )
            return _parse_assessment(agent, raw), stamp
        except Exception as exc:  # fail-safe: never drop an agent silently
            logger.warning("expert agent %s failed (%s); degraded assessment", agent, exc)
            stamp.status = "degraded"
            return degraded_assessment(agent, str(exc)), stamp


def run_expert_panel(
    envelope: WorkflowContext,
    qc,
    rc: RetrievedContext,
    brief: DraftBrief,
    settings: Settings | None = None,
) -> list[ExpertAssessment]:
    """Run the panel for this query in parallel. Assumes each agent is an expert on
    the (non-empty) panel returned by panel_for()."""
    settings = settings or get_settings()
    agents = panel_for(qc)
    if not agents:
        return []
    llm = get_llm(settings.expert_llm_tier, settings)
    assessor = ExpertAgent(llm, settings)

    def _run(agent: str) -> tuple[ExpertAssessment, ProvenanceStamp]:
        return assessor.assess(agent, envelope, qc, rc, brief)

    with ThreadPoolExecutor(max_workers=settings.expert_parallelism) as pool:
        results = list(pool.map(_run, agents))

    for _, stamp in results:
        envelope.stamp(stamp)
    return [assessment for assessment, _ in results]
