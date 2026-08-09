"""WorkflowContext envelope — the inter-agent communication format (agentic-workflow.md §2).

One envelope passes through the A1→A2→A3→A4 pipeline. Each agent reads its input
payload, writes its output payload, and appends a provenance stamp. No agent mutates
another agent's payload. The envelope is the audit record and is persisted per trace.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StageName(str, Enum):
    A1_ROUTER = "A1_router"
    A2_RETRIEVER = "A2_retriever"
    A3_SYNTHESIZER = "A3_synthesizer"
    A4_VALIDATOR = "A4_validator"
    ORCHESTRATOR = "orchestrator"


class StageStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"
    ESCALATED = "escalated"


class ProvenanceStamp(BaseModel):
    agent: str
    model: str
    prompt_version: str
    elapsed_ms: int = 0
    tokens: dict[str, int] = Field(default_factory=dict)
    attempt: int = 1
    status: str = "ok"


class StageInfo(BaseModel):
    name: StageName
    attempt: int = 1
    status: StageStatus = StageStatus.OK


class Control(BaseModel):
    revision_round: int = 0
    max_revision_rounds: int = 2
    cost_budget_usd: float = 1.00
    token_budget: int = 8000
    timeout_s: int = 90
    escalation_level: int = 0


class WorkflowInput(BaseModel):
    question: str
    channel: str = "api"  # slack | web | api
    user_id: str | None = None
    session_id: str | None = None
    attachments: list[str] = Field(default_factory=list)
    context_notes: str | None = None


class WorkflowContext(BaseModel):
    schema_version: str = "1.0"
    trace_id: str
    decision_id: str | None = None

    input: WorkflowInput
    stage: StageInfo
    payload: dict[str, Any] = Field(default_factory=dict)
    control: Control = Field(default_factory=Control)
    provenance: list[ProvenanceStamp] = Field(default_factory=list)

    def stamp(self, stamp: ProvenanceStamp) -> None:
        self.provenance.append(stamp)

    def set_stage(self, stage: StageName, status: StageStatus = StageStatus.OK, attempt: int = 1) -> None:
        self.stage = StageInfo(name=stage, status=status, attempt=attempt)
