"""Agent payloads — inter-agent contracts (agentic-workflow.md §2.3–2.4)."""

from typing import Optional

from pydantic import BaseModel, Field

CATEGORIES = {"procurement", "brand", "product", "hr", "legal", "ops"}
URGENCY = {"low", "medium", "high", "critical"}
FUNCTIONS = {
    "supply_chain", "finance", "legal", "brand", "product", "hr", "procurement", "ops",
}


class Entity(BaseModel):
    type: str
    name: str
    canonical_id: Optional[str] = None
    confidence: float = 0.0


class RetrievalDirectives(BaseModel):
    required_types: list[str] = Field(default_factory=list)
    preferred_recency_days: int = 540
    min_precedent_outcomes: bool = True


class QueryContext(BaseModel):
    """A1 output (agentic-workflow.md §2.3)."""

    category: str
    sub_category: str = ""
    category_confidence: float = 0.0
    category_evidence: str = ""
    brands: list[str] = Field(default_factory=lambda: ["all"])
    functions: list[str] = Field(default_factory=list)
    urgency: str = "low"
    required_expertise: list[str] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    intent: str = "decision_brief"  # decision_brief | answer | precedent_search
    retrieval_directives: RetrievalDirectives = Field(default_factory=RetrievalDirectives)
    clarifying_question: Optional[str] = None


class HistoricalDecision(BaseModel):
    decision_id: str
    title: str
    category: str = ""
    brands: list[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    outcome_summary: Optional[str] = None
    date: Optional[str] = None
    relevance: float = 0.0
    recency_bias: float = 0.0
    hybrid_score: float = 0.0
    match_reason: str = ""
    chunk_refs: list[str] = Field(default_factory=list)


class SimilarNegotiation(BaseModel):
    decision_id: str
    title: str
    match_reason: str = ""
    outcome: Optional[str] = None
    relevance: float = 0.0
    chunk_refs: list[str] = Field(default_factory=list)


class PlaybookSection(BaseModel):
    document_id: str
    section: str = ""
    chunk_id: str = ""
    relevance: float = 0.0
    applies_because: str = ""


class EvidenceGap(BaseModel):
    type: str  # missing_outcome | missing_docs | no_precedent | retrieval_empty
    description: str = ""


class GeneralChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str = ""
    content: str = ""
    doc_type: str = ""
    relevance: float = 0.0
    citation: str = ""


class RetrievalSummary(BaseModel):
    candidates_considered: int = 0
    reranked_top: int = 0
    evidence_coverage: dict[str, float] = Field(default_factory=dict)
    min_relevance: float = 0.0
    mode: str = "hybrid"  # hybrid | dense | sparse | degraded | empty
    note: Optional[str] = None


class RetrievedContext(BaseModel):
    """A2 output (agentic-workflow.md §2.4)."""

    retrieval_summary: RetrievalSummary = Field(default_factory=RetrievalSummary)
    historical_decisions: list[HistoricalDecision] = Field(default_factory=list)
    similar_negotiations: list[SimilarNegotiation] = Field(default_factory=list)
    playbook_sections: list[PlaybookSection] = Field(default_factory=list)
    general_context: list[GeneralChunk] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
