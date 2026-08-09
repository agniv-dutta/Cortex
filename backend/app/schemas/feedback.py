"""Feedback-loop API contracts (docs/feedback-loops.md §2–4)."""

from typing import Optional

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    action: str = Field(pattern="approved|rejected|deferred|overridden")
    reviewer: Optional[str] = None
    reason: Optional[str] = None


class ReviewResponse(BaseModel):
    decision_id: str
    action: str
    review_due_at: Optional[str] = None


class CalibrationBucket(BaseModel):
    bucket_low: float
    bucket_high: float
    count: int
    predicted_mean: float
    observed_rate: float


class CategoryAccuracy(BaseModel):
    category: str
    decisions: int
    outcomes: int
    coverage: float
    accuracy: float


class PrecedentUsefulness(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    used_count: int
    success_rate: float
    useful: bool


class BlindSpot(BaseModel):
    category: str
    reason: str
    failure_rate: float = 0.0
    coverage: float = 0.0


class OutcomeAnalysis(BaseModel):
    total_decisions: int
    outcomes_recorded: int
    overall_accuracy: float = 0.0
    accuracy_by_category: list[CategoryAccuracy] = Field(default_factory=list)
    accuracy_by_decision_class: list[CategoryAccuracy] = Field(default_factory=list)
    calibration: list[CalibrationBucket] = Field(default_factory=list)
    calibration_error: float = 0.0
    precedent_usefulness: list[PrecedentUsefulness] = Field(default_factory=list)
    blind_spots: list[BlindSpot] = Field(default_factory=list)


class MonthlyPoint(BaseModel):
    month: str
    value: float


class DashboardMetrics(BaseModel):
    decision_velocity: list[MonthlyPoint] = Field(default_factory=list)
    accuracy_trend: list[MonthlyPoint] = Field(default_factory=list)
    cost_savings_usd: float = 0.0
    outcomes_due: int = 0
    top_categories: list[CategoryAccuracy] = Field(default_factory=list)
    calibration_error: float = 0.0


class TopDecision(BaseModel):
    decision_id: str
    statement: str
    category: str
    outcome: str
    impact_usd: float = 0.0


class EmergingPattern(BaseModel):
    pattern: str
    evidence: str
    direction: str = ""


class MonthlyReport(BaseModel):
    month: str
    top_decisions: list[TopDecision] = Field(default_factory=list)
    emerging_patterns: list[EmergingPattern] = Field(default_factory=list)
    blind_spots: list[BlindSpot] = Field(default_factory=list)
    accuracy_summary: dict = Field(default_factory=dict)


class RetrainResponse(BaseModel):
    kind: str
    version: int
    samples: int
    metrics: dict = Field(default_factory=dict)


class FinetuneExportResponse(BaseModel):
    rows: int
    filename: str
    preview: list[dict] = Field(default_factory=list)
