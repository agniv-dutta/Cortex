"""Draft brief, validation, and escalation payloads (agentic-workflow.md §2.5–2.6,
prompts.md output schemas)."""

from typing import Optional

from pydantic import BaseModel, Field


class RecommendedAction(BaseModel):
    action: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    evidence_notes: str = ""
    alternatives: list["Alternative"] = Field(default_factory=list)


class Alternative(BaseModel):
    action: str
    tradeoff: str = ""


class Precedent(BaseModel):
    title: str
    decision_id: Optional[str] = None
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    why_applies: str = ""
    how_applies: str = ""
    outcome: Optional[str] = None
    relevance: float = 0.0
    citation: str = ""


class RiskFactor(BaseModel):
    type: str  # legal | financial | supply_chain | brand
    risk: str
    severity: str  # none|low|medium|high|critical
    likelihood: Optional[str] = None  # low|medium|high
    mitigation: Optional[str] = None
    source_chunk: Optional[str] = None


class ApprovalFlow(BaseModel):
    gates: list[str] = Field(default_factory=list)
    sla_hours: int = 24
    owner: Optional[str] = None


class DraftBrief(BaseModel):
    """A3 output (agentic-workflow.md §2.5)."""

    recommended_action: RecommendedAction
    precedents: list[Precedent] = Field(default_factory=list)  # exactly 3
    risk_factors: dict[str, RiskFactor] = Field(default_factory=dict)  # keyed by type
    approval_flow: ApprovalFlow = Field(default_factory=ApprovalFlow)
    evidence_gaps: list[str] = Field(default_factory=list)
    provenance_chunks: list[str] = Field(default_factory=list)


class ContradictionFlag(BaseModel):
    flag_type: str  # contradicts | supersedes | repeats_failure | no_precedent
    severity: str  # low | medium | high | critical
    rule_source: dict = Field(default_factory=dict)
    rule_quote: str = ""
    recommendation_quote: str = ""
    conflict_reason: str = ""
    resolution_required: Optional[str] = None
    citation: Optional[str] = None


class MissingContextAlert(BaseModel):
    type: str
    detail: str = ""
    severity: str = "low"


class ConfidenceChecks(BaseModel):
    evidence_density: float = 0.0
    citation_validity: float = 0.0
    confidence_rating: str = "adequate"  # adequate | low | inflated


class Validation(BaseModel):
    """A4 output (agentic-workflow.md §2.6)."""

    verdict: str  # pass | needs_revision | escalate
    contradiction_flags: list[ContradictionFlag] = Field(default_factory=list)
    missing_context_alerts: list[MissingContextAlert] = Field(default_factory=list)
    confidence_checks: ConfidenceChecks = Field(default_factory=ConfidenceChecks)
    revision_instructions: list[str] = Field(default_factory=list)
    escalation_reasons: list[str] = Field(default_factory=list)


class EscalationDecision(BaseModel):
    escalate: bool = False
    reviewer: list[str] = Field(default_factory=list)
    reason: str = ""
    conditions_to_defer: Optional[str] = None


class ModelInfo(BaseModel):
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    embedder: str = ""
    llm: str = ""
