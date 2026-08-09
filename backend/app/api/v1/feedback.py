"""Feedback-loop endpoints (docs/feedback-loops.md): human review, outcome-driven
analysis, dashboard, monthly report, and model retraining."""

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Decision
from app.schemas.feedback import (
    DashboardMetrics,
    FinetuneExportResponse,
    MonthlyReport,
    OutcomeAnalysis,
    RetrainResponse,
    ReviewRequest,
    ReviewResponse,
)
from app.services.feedback import (
    ConfidenceCalibrator,
    FeedbackRecorder,
    OutcomeAnalyzer,
    PrecedentStatsService,
    ReportingService,
    build_rows,
    export_filename,
)

router = APIRouter(tags=["feedback"])

EXPORT_DIR = Path(__file__).resolve().parents[3] / "data" / "exports"


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
    try:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        target = EXPORT_DIR / filename
        target.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    except OSError as exc:  # pragma: no cover — reporting only
        raise HTTPException(status_code=500, detail=f"export write failed: {exc}") from exc
    return FinetuneExportResponse(rows=len(rows), filename=filename, preview=preview)
