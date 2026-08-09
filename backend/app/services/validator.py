"""Agent 4 — Validation Agent (agentic-workflow.md §3.4, prompts.md §3).

Grounds the proposed recommendation against historical learnings and decisions
(retrieved fresh — the validator sees the raw chunks, not the synthesizer's
memory) and produces contradiction flags + confidence checks + verdict.
"""

import logging

from sqlalchemy.orm import Session

from app.core.envelope import ProvenanceStamp, StageName, StageStatus, WorkflowContext
from app.prompts import CONTRADICTION_SYSTEM, PROMPT_VERSION, contradiction_user
from app.providers.embedder import Embedder
from app.providers.llm import LLMProvider, get_llm
from app.schemas.brief import (
    ConfidenceChecks,
    ContradictionFlag,
    DraftBrief,
    MissingContextAlert,
    Validation,
)
from app.schemas.context import RetrievedContext
from app.services.jsonutil import parse_json_object

logger = logging.getLogger(__name__)

VALIDATION_PROMPT_VERSION = f"contradiction_v{PROMPT_VERSION}"

CRITICAL_FLAG_TYPES = {"contradicts", "repeats_failure"}


class ValidationAgent:
    def __init__(self, session: Session, embedder: Embedder) -> None:
        self.session = session
        self.embedder = embedder
        self.llm: LLMProvider = get_llm("premium")

    def validate(
        self,
        envelope: WorkflowContext,
        qc,
        rc: RetrievedContext,
        brief: DraftBrief,
    ) -> tuple[Validation, ProvenanceStamp]:
        stamp = ProvenanceStamp(agent=StageName.A4_VALIDATOR.value, model=self.llm.model, prompt_version=VALIDATION_PROMPT_VERSION)

        # ground truth pass: learnings + decisions are always re-retrieved fresh
        gt = self._ground_truth(qc, brief)

        import json as _json

        raw = self.llm.complete(
            CONTRADICTION_SYSTEM,
            contradiction_user(
                recommendation_json=_json.dumps(brief.recommended_action.model_dump()),
                category=qc.category,
                ground_truth_json=_json.dumps(gt, default=str),
            ),
            temperature=0.1,
            max_tokens=800,
            json_mode=True,
        )
        data = parse_json_object(raw)

        flags = [ContradictionFlag(**f) for f in data.get("contradictions") or []]
        checks = self._confidence_checks(brief, rc)
        alerts = [MissingContextAlert(type="outcome_unknown", detail="outcome data sparse")] if not self._any_outcome(rc) else []

        revision_instructions: list[str] = []
        escalation_reasons: list[str] = []
        verdict = "pass"

        for flag in flags:
            if flag.severity == "critical" or (flag.flag_type in CRITICAL_FLAG_TYPES and flag.severity == "high"):
                verdict = "escalate"
                escalation_reasons.append(
                    f"R3: recommendation {flag.flag_type}s active standing learning: {flag.conflict_reason}"
                )
                break
            if flag.severity == "high":
                verdict = "needs_revision"
                revision_instructions.append(
                    f"Re-answer under the standing constraint and surface the tradeoff explicitly: {flag.conflict_reason}"
                )

        if verdict != "escalate":
            if checks.evidence_density < 0.4:
                verdict = "needs_revision"
                revision_instructions.append(
                    "Lower recommendation confidence to <= 0.5 — evidence density is low."
                )
            elif not checks.citation_validity == 1.0:
                verdict = "needs_revision"
                revision_instructions.append("Remove or re-cite claims without a valid source chunk.")

        stamp.status = StageStatus.OK.value
        return (
            Validation(
                verdict=verdict,
                contradiction_flags=flags,
                missing_context_alerts=alerts,
                confidence_checks=checks,
                revision_instructions=revision_instructions,
                escalation_reasons=escalation_reasons,
            ),
            stamp,
        )

    def _ground_truth(self, qc, brief: DraftBrief) -> list[dict]:
        """Fresh retrieval of learnings + decision chunks to check against."""
        from app.providers.vectorstore import PgVectorStore

        store = PgVectorStore(self.session)
        vec = self.embedder.embed([brief.recommended_action.action])[0]
        hits = store.hybrid_search(
            vec,
            brief.recommended_action.action,
            category=qc.category,
            doc_types=["learning", "decision"],
            top_k=20,
        )
        return [
            {"title": h.title, "doc_type": h.doc_type, "citation": f"[{h.document_id}, {h.chunk_id}, {h.doc_type}]", "content": h.content}
            for h in hits
        ]

    @staticmethod
    def _confidence_checks(brief: DraftBrief, rc: RetrievedContext) -> ConfidenceChecks:
        known = {c.chunk_id for c in rc.general_context} | {
            p.chunk_id for p in rc.playbook_sections
        } | {d.chunk_refs[0] for d in rc.historical_decisions if d.chunk_refs}
        provenance = set(brief.provenance_chunks)
        if not provenance:
            return ConfidenceChecks(evidence_density=0.0, citation_validity=0.0, confidence_rating="low")
        validity = len(provenance & known) / len(provenance)
        return ConfidenceChecks(
            evidence_density=round(len(provenance) / max(1, len(rc.general_context) + 1), 2),
            citation_validity=round(validity, 2),
            confidence_rating="adequate" if validity >= 0.9 else "low",
        )

    @staticmethod
    def _any_outcome(rc: RetrievedContext) -> bool:
        return any(d.outcome for d in rc.historical_decisions)
