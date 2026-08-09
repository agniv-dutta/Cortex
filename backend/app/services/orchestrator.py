"""Workflow orchestrator (agentic-workflow.md §5) — deterministic DAG.

Run paths:
- run_query:    A1 Router → A2 Retriever → cheap grounded answer (or evidence-gap)
- run_decision: A1 → A2 → A3 Synthesizer ⇄ A4 Validator (bounded revision loop)
                → persistence (decision, brief, provenance, flags) → escalation

The envelope (WorkflowContext) is the audit record for the whole trace.
"""

import json
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.envelope import StageName, WorkflowContext, WorkflowInput
from app.core.ulid import gen_trace_id, new_id
from app.db.models import BriefChunk, Decision, DecisionBrief, Flag, Query
from app.prompts import ANSWER_SYSTEM, answer_user
from app.providers.embedder import Embedder, get_embedder
from app.providers.llm import get_llm
from app.schemas.api import Citation, DecisionResponse, QueryResponse
from app.schemas.brief import DraftBrief
from app.schemas.context import RetrievedContext
from app.services.escalation import EscalationService
from app.services.retriever import ContextRetriever
from app.services.router import QueryRouter
from app.services.synthesizer import DecisionSynthesizer, build_context_pack
from app.services.validator import ValidationAgent

logger = logging.getLogger(__name__)


class DecisionOrchestrator:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.embedder: Embedder = get_embedder()
        self.router = QueryRouter()
        self.retriever = ContextRetriever(session, self.embedder)
        self.synthesizer = DecisionSynthesizer(session, self.embedder)
        self.validator = ValidationAgent(session, self.embedder)
        self.escalation = EscalationService()

    # ------------------------------------------------------------------ #
    # envelope factory
    # ------------------------------------------------------------------ #
    @staticmethod
    def _envelope(question: str, channel: str, user_id: str | None, session_id: str | None, context_notes: str | None) -> WorkflowContext:
        return WorkflowContext(
            trace_id=gen_trace_id(),
            input=WorkflowInput(
                question=question, channel=channel, user_id=user_id,
                session_id=session_id, context_notes=context_notes,
            ),
            stage={"name": StageName.ORCHESTRATOR.value, "attempt": 1, "status": "ok"},
            control={"max_revision_rounds": get_settings().max_revision_rounds},
        )

    # ------------------------------------------------------------------ #
    # /v1/queries — grounded answer
    # ------------------------------------------------------------------ #
    def run_query(
        self,
        question: str,
        channel: str = "api",
        user_id: str | None = None,
        session_id: str | None = None,
        context_notes: str | None = None,
    ) -> QueryResponse:
        envelope = self._envelope(question, channel, user_id, session_id, context_notes)

        qc, stamp = self.router.route(envelope)
        envelope.stamp(stamp)

        if qc.clarifying_question:
            row = Query(id=new_id("qry"), question=question, channel=channel, user_id=user_id, session_id=session_id)
            self.session.add(row)
            self.session.commit()
            return QueryResponse(
                query_id=row.id, category=qc.category, category_confidence=qc.category_confidence,
                mode="clarify", clarifying_question=qc.clarifying_question,
            )

        rc, r_stamp = self.retriever.retrieve(envelope, qc)
        envelope.stamp(r_stamp)

        row = Query(
            id=new_id("qry"), user_id=user_id, channel=channel, question=question,
            category=qc.category, category_confidence=qc.category_confidence, session_id=session_id,
        )
        self.session.add(row)
        self.session.commit()

        if rc.retrieval_summary.mode == "empty":
            gaps = "; ".join(g.description for g in rc.evidence_gaps) or "no matching documents found"
            return QueryResponse(
                query_id=row.id, category=qc.category, category_confidence=qc.category_confidence,
                mode="evidence_gap",
                answer=f"Evidence gap: the corpus has no strong match for this question. {gaps}",
            )

        answer, citations = self._generate_answer(question, qc, rc)
        return QueryResponse(
            query_id=row.id, category=qc.category, category_confidence=qc.category_confidence,
            mode="answer", answer=answer, citations=citations,
        )

    def _generate_answer(self, question: str, qc, rc: RetrievedContext) -> tuple[str, list[Citation]]:
        llm = get_llm("cheap")
        context = build_context_pack(rc, self.settings.context_token_budget // 2)
        context_json = [
            {"citation": f"[{p['doc_id']}, {p['chunk_id']}, {p['doc_type']}]", "title": p["title"], "content": p["body"]}
            for p in context[:10]
        ]
        raw = llm.complete(
            ANSWER_SYSTEM, answer_user(question, json.dumps(context_json)),
            temperature=0.0, max_tokens=400, json_mode=False,
        )
        citations = [
            Citation(document_id=p["doc_id"], chunk_id=p["chunk_id"], title=p["title"], score=0.0)
            for p in context[:10]
        ]
        return raw.strip(), citations

    # ------------------------------------------------------------------ #
    # /v1/decisions — brief workflow
    # ------------------------------------------------------------------ #
    def run_decision(
        self,
        statement: str,
        category: str | None = None,
        decision_class: str | None = None,
        brands: list[str] | None = None,
        context_notes: str | None = None,
        requester: str | None = None,
    ) -> DecisionResponse:
        envelope = self._envelope(statement, "api", requester, None, context_notes)

        qc, stamp = self.router.route(envelope)
        envelope.stamp(stamp)
        if category:
            qc.category = category
        if decision_class:
            qc.sub_category = decision_class
        if brands and "all" not in brands:
            qc.brands = brands

        decision = Decision(
            id=new_id("dec"),
            statement=statement,
            category=qc.category,
            decision_class=qc.sub_category or qc.category,
            brands=qc.brands,
            requester=requester,
            context_notes=context_notes,
            status="draft",
        )
        self.session.add(decision)

        rc, r_stamp = self.retriever.retrieve(envelope, qc)
        envelope.stamp(r_stamp)

        if rc.retrieval_summary.mode == "empty":
            decision.status = "pending_review"
            self.session.commit()
            return DecisionResponse(
                decision_id=decision.id, status=decision.status,
                brief={"evidence_gap": [g.description for g in rc.evidence_gaps]},
                confidence=0.0,
            )

        # revision loop (agentic-workflow.md §5): A3 ⇄ A4, bounded
        brief: DraftBrief | None = None
        revision_instructions: list[str] = []
        final_flags = []
        verdict = "needs_revision"
        model_info = {"prompt_versions": {}, "embedder": self.embedder.model_version}

        while envelope.control.revision_round <= envelope.control.max_revision_rounds:
            brief, s_stamp = self.synthesizer.synthesize(envelope, qc, rc, revision_instructions or None)
            envelope.stamp(s_stamp)
            model_info["prompt_versions"]["brief"] = s_stamp.prompt_version
            model_info["llm"] = s_stamp.model

            validation, v_stamp = self.validator.validate(envelope, qc, rc, brief)
            envelope.stamp(v_stamp)
            model_info["prompt_versions"]["contradiction"] = v_stamp.prompt_version
            final_flags = [f.model_dump() for f in validation.contradiction_flags]

            verdict = validation.verdict
            if verdict == "pass":
                break
            if verdict == "escalate":
                break
            # needs_revision
            envelope.control.revision_round += 1
            if envelope.control.revision_round > envelope.control.max_revision_rounds:
                verdict = "escalate"
                validation.escalation_reasons.append("R1: revision loop exhausted")
                break
            revision_instructions = validation.revision_instructions

        brief = brief or DraftBrief(
            recommended_action={"action": "insufficient evidence", "confidence": 0.0}
        )

        # escalation
        esc, esc_stamp = self.escalation.decide(brief, validation.contradiction_flags, qc.category)
        envelope.stamp(esc_stamp)

        # persist
        brief_row = DecisionBrief(
            id=new_id("brf"),
            decision_id=decision.id,
            brief=brief.model_dump(),
            confidence=brief.recommended_action.confidence,
            model_info=model_info,
            status="pending_review" if (verdict == "escalate" or esc.escalate) else "draft",
            revision_round=envelope.control.revision_round,
        )
        self.session.add(brief_row)
        self.session.flush()

        for chunk_id in brief.provenance_chunks:
            self.session.add(BriefChunk(brief_id=brief_row.id, chunk_id=chunk_id, relevance=0.0))

        for flag in validation.contradiction_flags:
            self.session.add(
                Flag(
                    id=new_id("flg"),
                    brief_id=brief_row.id,
                    flag_type=flag.flag_type,
                    severity=flag.severity,
                    cited_chunk=flag.citation,
                    conflict_text=flag.conflict_reason,
                )
            )

        decision.status = brief_row.status
        self.session.commit()

        return DecisionResponse(
            decision_id=decision.id,
            status=decision.status,
            brief=brief.model_dump(),
            confidence=brief.recommended_action.confidence,
            flags=final_flags,
            provenance=brief.provenance_chunks,
            model_info=model_info,
        )
