"""Agent 2 — Context Retriever (agentic-workflow.md §3.2, retrieval-system.md).

Hybrid (dense + BM25) retrieval with category boost and freshness weighting,
plus deterministic query expansion (retrieval-system.md §5). Partitions results
into decisions / negotiations / playbook sections / general context and applies
the RETRIEVE_OK / WEAK / NONE thresholds.
"""

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.envelope import ProvenanceStamp, StageName, StageStatus, WorkflowContext
from app.providers.embedder import Embedder
from app.providers.vectorstore import PgVectorStore, ScoredChunk
from app.schemas.context import (
    EvidenceGap,
    GeneralChunk,
    HistoricalDecision,
    PlaybookSection,
    RetrievalSummary,
    RetrievedContext,
    SimilarNegotiation,
)

logger = logging.getLogger(__name__)


def expand_query(question: str, category: str, vendor: str | None) -> list[str]:
    """Deterministic query expansion (retrieval-system.md §5.3, mechanism 1)."""
    expansions: list[str] = []
    if vendor:
        expansions.extend(
            [
                f"{vendor} performance issues and SLAs",
                "Historical vendor transitions and outcomes",
                "Procurement policy for vendor changes and offboarding",
            ]
        )
    if category == "procurement":
        expansions.append("Vendor negotiation history and renewal terms")
    return expansions


class ContextRetriever:
    def __init__(self, session: Session, embedder: Embedder) -> None:
        self.session = session
        self.embedder = embedder
        self.store = PgVectorStore(session)
        self.settings = get_settings()

    def _run_search(
        self,
        text: str,
        embedding: list[float],
        qc: object,
        top_k: int,
    ) -> list[ScoredChunk]:
        return self.store.hybrid_search(
            embedding,
            text,
            category=getattr(qc, "category", None),
            brands=getattr(qc, "brands", None),
            doc_types=getattr(qc.retrieval_directives, "required_types", None) or None,
            top_k=top_k,
        )

    def retrieve(self, envelope: WorkflowContext, qc) -> tuple[RetrievedContext, ProvenanceStamp]:
        question = envelope.input.question
        stamp = ProvenanceStamp(agent=StageName.A2_RETRIEVER.value, model=self.embedder.model_version, prompt_version="retriever_v1")

        vendor = next((e.name for e in qc.entities if e.type == "vendor"), None)
        expansions = expand_query(question, qc.category, vendor)

        all_texts = [question] + expansions
        vectors = self.embedder.embed(all_texts)

        candidates: dict[str, ScoredChunk] = {}
        weights = [1.0] + [0.6] * len(expansions)
        for text, vec, weight in zip(all_texts, vectors, weights):
            hits = self._run_search(text, vec, qc, top_k=20)
            for hit in hits:
                if hit.chunk_id not in candidates:
                    candidates[hit.chunk_id] = hit
                candidates[hit.chunk_id].hybrid_score = max(
                    candidates[hit.chunk_id].hybrid_score, hit.hybrid_score * weight
                )

        ranked = sorted(candidates.values(), key=lambda c: c.hybrid_score, reverse=True)

        # thresholds (retrieval-system.md §3.6)
        top_score = ranked[0].hybrid_score if ranked else 0.0
        ok_threshold = self.settings.retrieve_ok_threshold
        weak_threshold = self.settings.retrieve_weak_threshold
        mode = "hybrid"
        note = None
        if not ranked or top_score < weak_threshold:
            mode = "empty"
            note = "no strong match in corpus (RETRIEVE_NONE)"
        elif top_score < ok_threshold:
            mode = "hybrid"
            note = "weak evidence (RETRIEVE_WEAK) — confidence must be low"

        rc = self._partition(ranked, mode, note, len(vectors))
        if not ranked:
            rc.evidence_gaps.append(EvidenceGap(type="retrieval_empty", description=note or "no candidates"))
        if not any(d.outcome for d in rc.historical_decisions):
            rc.evidence_gaps.append(
                EvidenceGap(type="missing_outcome", description="no historical decision with a recorded outcome matched")
            )
        stamp.status = StageStatus.OK.value
        return rc, stamp

    def _partition(self, ranked: list[ScoredChunk], mode: str, note: str | None, queries_used: int) -> RetrievedContext:
        decisions: list[HistoricalDecision] = []
        negotiations: list[SimilarNegotiation] = []
        playbooks: list[PlaybookSection] = []
        general: list[GeneralChunk] = []

        for chunk in ranked:
            doc_type = chunk.doc_type
            if doc_type == "decision" and len(decisions) < 5:
                decisions.append(
                    HistoricalDecision(
                        decision_id=chunk.document_id,
                        title=chunk.title,
                        category=chunk.category or "",
                        outcome=None,
                        date=str(chunk.created_at.date()) if chunk.created_at else None,
                        relevance=round(chunk.hybrid_score, 3),
                        hybrid_score=round(chunk.hybrid_score, 3),
                        match_reason="",
                        chunk_refs=[chunk.chunk_id],
                    )
                )
            elif doc_type in {"negotiation", "vendor"} and len(negotiations) < 5:
                negotiations.append(
                    SimilarNegotiation(
                        decision_id=chunk.document_id,
                        title=chunk.title,
                        match_reason="",
                        relevance=round(chunk.hybrid_score, 3),
                        chunk_refs=[chunk.chunk_id],
                    )
                )
            elif doc_type == "playbook" and len(playbooks) < 5:
                playbooks.append(
                    PlaybookSection(
                        document_id=chunk.document_id,
                        section=chunk.title,
                        chunk_id=chunk.chunk_id,
                        relevance=round(chunk.hybrid_score, 3),
                        applies_because="",
                    )
                )
            else:
                general.append(
                    GeneralChunk(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        title=chunk.title,
                        content=chunk.content,
                        doc_type=doc_type,
                        relevance=round(chunk.hybrid_score, 3),
                        citation=f"[{chunk.document_id}, {chunk.chunk_id}, {doc_type}]",
                    )
                )

        coverage = {}
        if ranked:
            for t in {c.doc_type for c in ranked}:
                coverage[t] = round(sum(1 for c in ranked if c.doc_type == t) / len(ranked), 2)

        summary = RetrievalSummary(
            candidates_considered=len(ranked),
            reranked_top=len(ranked[: self.settings.context_top_k]),
            evidence_coverage=coverage,
            min_relevance=round(ranked[-1].hybrid_score, 3) if ranked else 0.0,
            mode=mode,
            note=note,
        )
        return RetrievedContext(
            retrieval_summary=summary,
            historical_decisions=decisions,
            similar_negotiations=negotiations,
            playbook_sections=playbooks,
            general_context=general,
        )
