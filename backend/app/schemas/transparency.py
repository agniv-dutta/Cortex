"""Decision transparency payloads for provenance and validation UI."""

from typing import Optional

from pydantic import BaseModel, Field


class RetrievedDocumentInsight(BaseModel):
    id: str
    title: str
    source: str
    relevanceScore: float = 0.0
    explanation: str = ""
    note: Optional[str] = None


class PlaybookCheckItem(BaseModel):
    check: str
    passed: bool
    detail: str = ""


class MissingDataItem(BaseModel):
    label: str
    detail: str = ""


class ConfidenceReasoningItem(BaseModel):
    summary: str
    detail: str = ""


class DecisionTransparency(BaseModel):
    retrievedDocuments: list[RetrievedDocumentInsight] = Field(default_factory=list)
    confidenceReasoning: list[ConfidenceReasoningItem] = Field(default_factory=list)
    playbookChecks: list[PlaybookCheckItem] = Field(default_factory=list)
    missingData: list[MissingDataItem] = Field(default_factory=list)
