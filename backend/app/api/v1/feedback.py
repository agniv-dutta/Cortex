"""Feedback-loop endpoints (docs/feedback-loops.md): human review, outcome-driven
analysis, dashboard, monthly report, and model retraining."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Decision
from app.schemas.feedback import (
    DashboardMetrics,
    FinetuneDatasetResponse,
    FinetuneExportRequest,
    FinetuneExportResponse,
    MonthlyReport,
    OutcomeAnalysis,
    RetrainResponse,
    ReviewRequest,
    ReviewResponse,
    Think9EvalRequest,
    Think9EvalResult,
    Think9ModelRegisterRequest,
    Think9ModelResponse,
    Think9ModelStatusResponse,
)
from app.services.feedback import (
    ConfidenceCalibrator,
    FeedbackRecorder,
    OutcomeAnalyzer,
    PrecedentStatsService,
    ReportingService,
    Think9ModelService,
    build_rows,
    export_filename,
)

router = APIRouter(tags=["feedback"])


@router.post("/decisions/{decision_id}/review", response_model=ReviewResponse)
def review_decision(decision_id: str, body: ReviewRequest, db: Session = Depends(get_db)) -> ReviewResponse:
    try:
        event = FeedbackRecorder().record_review(
            db, decision_id, body.action, body.reviewer, body.reason
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    decision = db.get(Decision, decision_id)
    return ReviewResponse(
        decision_id=decision_id,
        action=event.action,
        review_due_at=decision.review_due_at.isoformat() if decision.review_due_at else None,
    )


@router.get("/admin/analysis", response_model=OutcomeAnalysis)
def outcome_analysis(db: Session = Depends(get_db)) -> OutcomeAnalysis:
    return OutcomeAnalyzer().analyze(db)


@router.get("/admin/dashboard", response_model=DashboardMetrics)
def dashboard(db: Session = Depends(get_db)) -> DashboardMetrics:
    return ReportingService(db).dashboard()


@router.get("/admin/report/monthly", response_model=MonthlyReport)
def monthly_report(month: str | None = None, db: Session = Depends(get_db)) -> MonthlyReport:
    return ReportingService(db).monthly_report(month)


@router.post("/admin/calibration/retrain", response_model=RetrainResponse)
def retrain_calibration(db: Session = Depends(get_db)) -> RetrainResponse:
    calibrator = ConfidenceCalibrator()
    payload, metrics, version = calibrator.retrain(db)
    return RetrainResponse(
        kind="confidence",
        version=version,
        samples=payload.get("samples", 0),
        metrics=metrics,
    )


@router.post("/admin/ranking/rebuild")
def rebuild_precedent_stats(db: Session = Depends(get_db)) -> dict:
    count = PrecedentStatsService.rebuild(db)
    return {"rebuild": True, "chunks_scored": count}


@router.get("/admin/finetune/export", response_model=FinetuneExportResponse)
def finetune_export(db: Session = Depends(get_db)) -> FinetuneExportResponse:
    rows = build_rows(db)
    filename = export_filename()
    preview = rows[:5]
    return FinetuneExportResponse(rows=len(rows), filename=filename, preview=preview)


@router.post("/admin/finetune/dataset", response_model=FinetuneDatasetResponse)
def finetune_dataset(body: FinetuneExportRequest, db: Session = Depends(get_db)) -> FinetuneDatasetResponse:
    return Think9ModelService(db).export_dataset(
        holdout_fraction=body.holdout_fraction,
        min_samples=body.min_samples,
    )


@router.post("/admin/finetune/evaluate", response_model=Think9EvalResult)
def finetune_evaluate(body: Think9EvalRequest, db: Session = Depends(get_db)) -> Think9EvalResult:
    return Think9ModelService(db).evaluate(
        mode=body.mode,
        sample_size=body.sample_size,
        holdout_fraction=body.holdout_fraction,
        candidate_provider=body.candidate_provider,
        candidate_model=body.candidate_model,
        baseline_provider=body.baseline_provider,
        baseline_model=body.baseline_model,
    )


@router.post("/admin/finetune/deploy", response_model=Think9ModelResponse)
def finetune_deploy(body: Think9ModelRegisterRequest, db: Session = Depends(get_db)) -> Think9ModelResponse:
    return Think9ModelService(db).register_model(body)


@router.get("/admin/finetune/status", response_model=Think9ModelStatusResponse)
def finetune_status(db: Session = Depends(get_db)) -> Think9ModelStatusResponse:
    return Think9ModelService(db).status()

