"""HTTP API contracts (decision-intelligence-mvp.md §8)."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    channel: str = "api"  # slack | web | api
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    context_notes: Optional[str] = None


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    title: str = ""
    score: float = 0.0


class QueryResponse(BaseModel):
    query_id: str
    category: str
    category_confidence: float
    mode: str = "answer"  # answer | brief | evidence_gap
    answer: Optional[str] = None
    citations: list[Citation] = Field(default_factory=list)
    clarifying_question: Optional[str] = None


class DecisionCreateRequest(BaseModel):
    statement: str = Field(min_length=3, max_length=4000)
    category: Optional[str] = None
    decision_class: Optional[str] = None
    brands: list[str] = Field(default_factory=list)
    context_notes: Optional[str] = None
    requester: Optional[str] = None


class DecisionResponse(BaseModel):
    decision_id: str
    status: str
    brief: Optional[dict[str, Any]] = None
    confidence: Optional[float] = None
    flags: list[dict[str, Any]] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    model_info: Optional[dict[str, Any]] = None
    assessments: list[dict[str, Any]] = Field(default_factory=list)
    meta: Optional[dict[str, Any]] = None


class OutcomeRequest(BaseModel):
    result: str  # success | partial | failure | superseded
    metric_deltas: dict[str, Any] = Field(default_factory=dict)
    narrative: Optional[str] = None
    recorded_by: Optional[str] = None


class SearchRequest(BaseModel):
    q: str = Field(min_length=2, max_length=1000)
    category: Optional[str] = None
    brands: Optional[list[str]] = None
    doc_type: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    source: str = ""
    date: Optional[str] = None


class SearchResponse(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)
    total: int = 0


class IngestRequest(BaseModel):
    source: str  # drive | zoom | slack | gmail | airtable | manual
    source_ref: dict[str, Any] = Field(default_factory=dict)
    force_reprocess: bool = False


class IngestResponse(BaseModel):
    job_id: str
    status: str = "queued"
    stages: list[str] = Field(default_factory=list)
