"""Scenario simulation payloads for "What if" analysis."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ScenarioRequest(BaseModel):
    """Request for scenario simulation."""
    
    question: str = Field(min_length=10, max_length=2000, description="What if question")
    scenario_type: Literal["pricing", "vendor", "supply", "capacity", "financial", "strategic"] = Field(
        description="Type of scenario to simulate"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Scenario-specific parameters (e.g., MOQ quantity, price change %)"
    )
    brands: list[str] = Field(default_factory=list, description="Brands to include in analysis")
    time_horizon: Literal["1q", "2q", "1y", "2y"] = Field(default="1y", description="Time horizon for impact")
    include_financials: bool = Field(default=True, description="Include financial impact analysis")
    include_risk: bool = Field(default=True, description="Include risk assessment")


class FinancialImpact(BaseModel):
    """Financial impact of a scenario."""
    
    impact_type: str
    description: str
    magnitude: float  # Could be positive or negative
    unit: str  # "$", "%", "basis points"
    confidence: float  # 0-1
    drivers: list[str] = Field(default_factory=list)


class RiskImpact(BaseModel):
    """Risk impact of a scenario."""
    
    risk_type: str
    severity: Literal["low", "medium", "high", "critical"]
    likelihood: Literal["low", "medium", "high"]
    description: str
    mitigation: str | None = None


class HistoricalAnalogue(BaseModel):
    """Historical precedent similar to the scenario."""
    
    decision_id: str
    title: str
    date: str
    similarity: float  # 0-1
    outcome: str
    key_factors: list[str] = Field(default_factory=list)
    lessons_learned: list[str] = Field(default_factory=list)


class OutcomeProbability(BaseModel):
    """Estimated probability of different outcomes."""
    
    outcome: str
    probability: float  # 0-1
    rationale: str
    confidence_interval: tuple[float, float] | None = None


class ScenarioResponse(BaseModel):
    """Response to scenario simulation query."""
    
    scenario_id: str
    question: str
    scenario_type: str
    summary: str
    financial_impacts: list[FinancialImpact] = Field(default_factory=list)
    risk_impacts: list[RiskImpact] = Field(default_factory=list)
    historical_analogues: list[HistoricalAnalogue] = Field(default_factory=list)
    outcome_probabilities: list[OutcomeProbability] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float  # Overall confidence in the analysis
    assumptions: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    model_info: dict[str, Any] = Field(default_factory=dict)
