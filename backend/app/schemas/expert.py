"""Expert-agent payloads (docs/expert-agents.md §1–4): per-agent assessments and
the meta-agent synthesis output. These are the E1 → E2 inter-agent contracts."""

from typing import Optional

from pydantic import BaseModel, Field

VERDICTS = {"support", "conditionally_support", "oppose"}
AGENT_NAMES = {"legal", "financial", "supply_chain", "brand", "operations"}
SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class ExpertRisk(BaseModel):
    risk: str
    severity: str = "low"  # none|low|medium|high|critical
    likelihood: str = ""  # low|medium|high
    impact: str = ""
    evidence: str = ""
    mitigation: str = ""


class ExpertOpportunity(BaseModel):
    opportunity: str
    value: str = ""
    evidence: str = ""


class ExpertConstraint(BaseModel):
    constraint: str
    type: str = "soft"  # hard|soft
    reason: str = ""
    owner: str = ""


class EscalationFlag(BaseModel):
    flag: bool = False
    reason: str = ""
    to: str = ""  # legal_counsel | cfo | supply_chain_manager | brand_lead | ops_head | executive


class ExpertAssessment(BaseModel):
    """E1 output — one per agent (docs/expert-agents.md §2)."""

    agent: str
    verdict: str = "conditionally_support"
    summary: str = ""
    risks: list[ExpertRisk] = Field(default_factory=list)
    opportunities: list[ExpertOpportunity] = Field(default_factory=list)
    constraints: list[ExpertConstraint] = Field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.0
    escalate: EscalationFlag = Field(default_factory=EscalationFlag)
    assumptions: list[str] = Field(default_factory=list)
    status: str = "ok"  # ok | degraded


class Conflict(BaseModel):
    between: list[str] = Field(default_factory=list)
    type: str = "verdict"  # verdict | hard_constraint | risk_severity
    detail: str = ""
    resolved: bool = False
    resolution: str = ""


class MetaEscalation(BaseModel):
    agent: str = ""
    reason: str = ""
    to: str = ""


class MetaSynthesis(BaseModel):
    """E2 output (docs/expert-agents.md §4)."""

    unified_brief: dict[str, object] = Field(default_factory=dict)
    agreement: float = 0.0
    conflicts: list[Conflict] = Field(default_factory=list)
    escalations: list[MetaEscalation] = Field(default_factory=list)
    final_confidence: float = 0.0
    final_status: str = "approve"  # approve | conditionally_approve | escalate
    unresolved_conflicts: list[str] = Field(default_factory=list)
    note: Optional[str] = None
