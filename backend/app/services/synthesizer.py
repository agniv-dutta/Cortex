"""Agent 3 — Decision Synthesizer (agentic-workflow.md §3.3, prompts.md §2).

Builds the packed context from retrieved chunks, calls the premium-tier LLM to
produce the draft brief, parses + validates it, and enforces citation integrity
(every provenance chunk must exist in the retrieved context).
"""

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.envelope import ProvenanceStamp, StageName, WorkflowContext
from app.prompts import BRIEF_SYSTEM, PROMPT_VERSION, THINK9_BRIEF_SYSTEM, brief_user
from app.providers.embedder import Embedder
from app.providers.llm import LLMProvider, get_llm
from app.schemas.brief import DraftBrief
from app.schemas.context import RetrievedContext
from app.services.jsonutil import parse_json_object

logger = logging.getLogger(__name__)

BRIEF_PROMPT_VERSION = f"brief_v{PROMPT_VERSION}"


def build_context_pack(rc: RetrievedContext, token_budget: int = 4000) -> list[dict]:
    """Order: decisions-with-outcome first, then playbooks, then general context.
    Truncate when the approximate token budget is hit (~1.3 chars/token)."""
    packed: list[dict] = []
    budget_chars = token_budget * 4

    def push(kind: str, chunk_id: str, doc_id: str, doc_type: str, title: str, body: str) -> bool:
        nonlocal budget_chars
        if len(body) > budget_chars:
            return False
        packed.append(
            {
                "kind": kind,
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "doc_type": doc_type,
                "title": title,
                "body": body,
            }
        )
        budget_chars -= len(body)
        return True

    ordered_decisions = sorted(
        rc.historical_decisions, key=lambda d: d.outcome is None
    )
    for d in ordered_decisions[:3]:
        push("decision", d.chunk_refs[0] if d.chunk_refs else "", d.decision_id, "decision", d.title, d.match_reason or d.title)
    for p in rc.playbook_sections[:5]:
        push("playbook", p.chunk_id, p.document_id, "playbook", p.section, p.applies_because or p.section)
    for c in rc.general_context:
        push("general", c.chunk_id, c.document_id, c.doc_type, c.title, c.content)
    return packed


class DecisionSynthesizer:
    def __init__(self, session: Session, embedder: Embedder, llm_override: LLMProvider | None = None) -> None:
        self.session = session
        self.embedder = embedder
        self.llm_override = llm_override
        self.llm: LLMProvider = llm_override or get_llm("brief")

    def synthesize(
        self,
        envelope: WorkflowContext,
        qc,
        rc: RetrievedContext,
        revision_instructions: list[str] | None = None,
    ) -> tuple[DraftBrief, ProvenanceStamp]:
        stamp = ProvenanceStamp(agent=StageName.A3_SYNTHESIZER.value, model=self.llm.model, prompt_version=BRIEF_PROMPT_VERSION)

        packed = build_context_pack(rc, self.settings().context_token_budget)
        rc_json = [
            {
                "kind": p["kind"],
                "citation": f"[{p['doc_id']}, {p['chunk_id']}, {p['doc_type']}]",
                "title": p["title"],
                "content": p["body"],
            }
            for p in packed
        ]

        user = brief_user(
            question=envelope.input.question,
            category=qc.category,
            sub_category=getattr(qc, "sub_category", ""),
            brands=",".join(qc.brands),
            urgency=qc.urgency,
            context_notes=envelope.input.context_notes or "",
            retrieved_context_json=_dump(rc_json),
        )
        if revision_instructions:
            user += "\n\nREVISION INSTRUCTIONS (must be honored):\n- " + "\n- ".join(revision_instructions)

        raw = self.llm.complete(
            THINK9_BRIEF_SYSTEM if self.llm_override is not None else BRIEF_SYSTEM,
            user,
            temperature=0.2,
            max_tokens=1600,
            json_mode=True,
        )
        data = parse_json_object(raw)
        brief = DraftBrief.model_validate(self._normalize(data))

        # citation integrity: only chunks that exist in retrieved context are kept
        known = {p["chunk_id"] for p in packed}
        llm_provenance = [c for c in (data.get("provenance_chunks") or []) if c in known]
        brief.provenance_chunks = llm_provenance or [p["chunk_id"] for p in packed]
        if len(brief.precedents) < 3:
            brief.evidence_gaps.append(
                f"only {len(brief.precedents)}/3 precedents available in retrieved context"
            )
        stamp.elapsed_ms = 0
        return brief, stamp

    @staticmethod
    def _normalize(data: dict) -> dict:
        ra = data.get("recommended_action") or {}
        return {
            "recommended_action": {
                "action": ra.get("action", ""),
                "confidence": float(ra.get("confidence", 0.0)),
                "rationale": ra.get("rationale", ""),
                "evidence_notes": ra.get("evidence_notes", ""),
                "alternatives": [
                    {"action": a.get("action", ""), "tradeoff": a.get("tradeoff", "")}
                    for a in (ra.get("alternatives") or [])
                ],
            },
            "precedents": [
                {
                    "title": p.get("title", ""),
                    "decision_id": p.get("decision_id"),
                    "document_id": p.get("document_id"),
                    "chunk_id": p.get("chunk_id"),
                    "why_applies": p.get("why_applies", ""),
                    "how_applies": p.get("how_applies", ""),
                    "outcome": p.get("outcome"),
                    "relevance": float(p.get("relevance", 0.0)),
                    "citation": p.get("citation", ""),
                }
                for p in (data.get("precedents") or [])
            ],
            "risk_factors": {
                t: {
                    "type": t,
                    "risk": (data.get("risk_factors") or {}).get(t, {}).get("risk", "none identified"),
                    "severity": (data.get("risk_factors") or {}).get(t, {}).get("severity", "none"),
                    "likelihood": (data.get("risk_factors") or {}).get(t, {}).get("likelihood"),
                    "mitigation": (data.get("risk_factors") or {}).get(t, {}).get("mitigation"),
                    "source_chunk": (data.get("risk_factors") or {}).get(t, {}).get("source_chunk"),
                }
                for t in ["legal", "financial", "supply_chain", "brand"]
            },
            "approval_flow": {
                "gates": (data.get("approval_flow") or {}).get("gates", []),
                "sla_hours": int((data.get("approval_flow") or {}).get("sla_hours", 24)),
            },
            "evidence_gaps": data.get("evidence_gaps") or [],
            "provenance_chunks": data.get("provenance_chunks") or [],
        }

    @staticmethod
    def settings():
        return get_settings()


def _dump(obj) -> str:
    import json

    return json.dumps(obj)
