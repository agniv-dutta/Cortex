"""Portfolio intelligence payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PortfolioIntelligenceRequest(BaseModel):
    brands: list[str] = Field(default_factory=list)
    since_days: int = Field(default=180, ge=1, le=1825)
    min_brands: int = Field(default=3, ge=2, le=50)
    min_score: float = Field(default=0.6, ge=0.0, le=1.0)
    report_type: Literal["ad_hoc", "monthly"] = "ad_hoc"
    persist_alerts: bool = False


class PortfolioEvidence(BaseModel):
    document_id: str
    chunk_id: str
    doc_type: str
    title: str
    brand: str
    snippet: str = ""
    signal_kind: str = ""


class PortfolioCluster(BaseModel):
    cluster_id: str
    dimension: str
    key: str
    title: str
    summary: str
    affected_brands: list[str] = Field(default_factory=list)
    document_count: int = 0
    evidence_count: int = 0
    score: float = 0.0
    drivers: list[str] = Field(default_factory=list)
    evidence: list[PortfolioEvidence] = Field(default_factory=list)
    recommended_action: str = ""
    execution_target: str = ""


class PortfolioOpportunity(PortfolioCluster):
    opportunity_type: str = "consolidation"


class PortfolioRisk(PortfolioCluster):
    risk_type: str = "portfolio_concentration"
    blast_radius: int = 0


class ExecutionTrigger(BaseModel):
    trigger_id: str
    action: str
    target: str
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    reason: str
    linked_cluster_ids: list[str] = Field(default_factory=list)
    should_execute: bool = False


class PortfolioSummary(BaseModel):
    total_brands_scanned: int = 0
    total_documents_scanned: int = 0
    clusters_found: int = 0
    opportunities_found: int = 0
    risks_found: int = 0
    triggers_fired: int = 0
    estimated_value_created: float = 0.0


class PortfolioIntelligenceResponse(BaseModel):
    report_type: Literal["ad_hoc", "monthly"]
    generated_at: datetime
    summary: PortfolioSummary = Field(default_factory=PortfolioSummary)
    clusters: list[PortfolioCluster] = Field(default_factory=list)
    opportunities: list[PortfolioOpportunity] = Field(default_factory=list)
    risks: list[PortfolioRisk] = Field(default_factory=list)
    triggers: list[ExecutionTrigger] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

