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


class ModelDriftSeries(BaseModel):
    win_rate: list[MonthlyPoint] = Field(default_factory=list)
    match_delta: list[MonthlyPoint] = Field(default_factory=list)
    confidence_mae_delta: list[MonthlyPoint] = Field(default_factory=list)
    citation_overlap_delta: list[MonthlyPoint] = Field(default_factory=list)
    format_compliance_delta: list[MonthlyPoint] = Field(default_factory=list)


class ModelDriftReport(ModelDriftSeries):
    runs_recorded: int = 0
    latest_eval: dict = Field(default_factory=dict)
    latest_train: dict = Field(default_factory=dict)
    latest_deploy: dict = Field(default_factory=dict)


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
    model_drift: ModelDriftReport = Field(default_factory=ModelDriftReport)


class RetrainResponse(BaseModel):
    kind: str
    version: int
    samples: int
    metrics: dict = Field(default_factory=dict)


class FinetuneExportResponse(BaseModel):
    rows: int
    filename: str
    preview: list[dict] = Field(default_factory=list)


class FinetuneExportRequest(BaseModel):
    holdout_fraction: float = Field(default=0.2, ge=0.05, le=0.5)
    min_samples: int = Field(default=200, ge=10, le=10000)
    format: str = Field(default="jsonl", pattern="jsonl|json")


class FinetuneExample(BaseModel):
    instruction: str
    input: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)
    messages: list[dict] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class FinetuneDatasetResponse(BaseModel):
    rows: int
    filename: str
    holdout_rows: int
    training_rows: int
    preview: list[FinetuneExample] = Field(default_factory=list)
    manifest: dict = Field(default_factory=dict)


class Think9ModelRegisterRequest(BaseModel):
    role: str = "decision_brief"
    provider: str
    model_name: str
    base_model: Optional[str] = None
    dataset_version: Optional[str] = None
    notes: Optional[str] = None
    activate: bool = True


class Think9ModelResponse(BaseModel):
    id: str
    role: str
    provider: str
    model_name: str
    base_model: Optional[str] = None
    dataset_version: Optional[str] = None
    active: bool = False
    samples: int = 0
    train_metrics: dict = Field(default_factory=dict)
    eval_metrics: dict = Field(default_factory=dict)
    notes: Optional[str] = None
    created_at: Optional[str] = None


class Think9EvalRequest(BaseModel):
    mode: str = Field(default="historical", pattern="historical|live|ab")
    sample_size: int = Field(default=25, ge=1, le=200)
    holdout_fraction: float = Field(default=0.2, ge=0.05, le=0.5)
    candidate_provider: Optional[str] = None
    candidate_model: Optional[str] = None
    baseline_provider: Optional[str] = None
    baseline_model: Optional[str] = None


class Think9EvalResult(BaseModel):
    candidate: dict = Field(default_factory=dict)
    baseline: dict = Field(default_factory=dict)
    comparison: dict = Field(default_factory=dict)
    samples: int = 0
    latency_ms_p50: float = 0.0
    latency_ms_p95: float = 0.0
    cost_usd_candidate: float = 0.0
    cost_usd_baseline: float = 0.0


class Think9ModelStatusResponse(BaseModel):
    active: Optional[Think9ModelResponse] = None
    history: list[Think9ModelResponse] = Field(default_factory=list)


class Think9TrainRequest(BaseModel):
    role: str = "decision_brief"
    provider: str
    model_name: str
    base_model: Optional[str] = None
    holdout_fraction: float = Field(default=0.2, ge=0.05, le=0.5)
    min_samples: int = Field(default=200, ge=10, le=10000)
    activate_on_success: bool = False
    notes: Optional[str] = None


class Think9TrainResponse(BaseModel):
    run_id: str
    task_id: Optional[str] = None
    status: str
    dataset_version: str
    samples: int = 0
    training_rows: int = 0
    holdout_rows: int = 0
    manifest: dict = Field(default_factory=dict)
    plan: dict = Field(default_factory=dict)
