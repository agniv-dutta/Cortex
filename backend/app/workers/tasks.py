"""Celery tasks - async decision brief generation and Think9 fine-tune runs.

Runs outside the request cycle; opens its own DB session (engine pool shared).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.database import SessionLocal
from app.db.models.feedback import FineTuneRun
from app.schemas.feedback import Think9TrainRequest
from app.schemas.portfolio import PortfolioIntelligenceRequest
from app.services.decision_aggregation import DecisionAggregationService
from app.services.feedback.think9_model import (
    _planned_dataset_version,
    _training_plan,
    build_dataset,
    export_filename,
)
from app.services.orchestrator import DecisionOrchestrator
from app.services.portfolio import PortfolioIntelligenceService

from app.workers.celery_app import celery_app  # noqa: E402

logger = logging.getLogger(__name__)


@celery_app.task(name="decisions.generate_brief")
def generate_brief_task(
    statement: str,
    category: str | None = None,
    decision_class: str | None = None,
    brands: list[str] | None = None,
    context_notes: str | None = None,
    requester: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        orchestrator = DecisionOrchestrator(db)
        result = orchestrator.run_decision(
            statement=statement,
            category=category,
            decision_class=decision_class,
            brands=brands,
            context_notes=context_notes,
            requester=requester,
        )
        return {"decision_id": result.decision_id, "status": result.status, "confidence": result.confidence}
    finally:
        db.close()


@celery_app.task(name="portfolio.generate_report")
def generate_portfolio_report_task(
    brands: list[str] | None = None,
    since_days: int = 180,
    min_brands: int = 3,
    min_score: float = 0.6,
    report_type: str = "monthly",
    persist_alerts: bool = True,
) -> dict:
    db = SessionLocal()
    try:
        service = PortfolioIntelligenceService(db)
        report = service.generate_report(
            PortfolioIntelligenceRequest(
                brands=brands or [],
                since_days=since_days,
                min_brands=min_brands,
                min_score=min_score,
                report_type=report_type,  # type: ignore[arg-type]
                persist_alerts=persist_alerts,
            )
        )
        return report.model_dump()
    finally:
        db.close()


@celery_app.task(name="decisions.scan_patterns")
def scan_decision_patterns_task(
    since_days: int = 30,
    brands: list[str] | None = None,
    min_brands: int = 2,
    min_score: float = 0.6,
) -> dict:
    """Background task to scan decisions for multi-brand patterns."""
    db = SessionLocal()
    try:
        service = DecisionAggregationService(db)
        report = service.scan_decisions(
            since_days=since_days,
            brands=brands,
            min_brands=min_brands,
            min_score=min_score,
            report_type="ad_hoc",
        )
        logger.info(
            f"Decision pattern scan completed: {report.summary.clusters_found} clusters, "
            f"{report.summary.opportunities_found} opportunities, "
            f"${report.summary.estimated_value_created:,.2f} estimated value"
        )
        return report.model_dump()
    finally:
        db.close()


@celery_app.task(name="decisions.monthly_report")
def generate_decision_monthly_report_task(
    month: int | None = None,
    year: int | None = None,
) -> dict:
    """Background task to generate monthly cross-portfolio value report."""
    db = SessionLocal()
    try:
        service = DecisionAggregationService(db)
        report = service.generate_monthly_report(month=month, year=year)
        logger.info(
            f"Monthly decision report generated: {report.summary.clusters_found} clusters, "
            f"{report.summary.opportunities_found} opportunities, "
            f"${report.summary.estimated_value_created:,.2f} estimated value created"
        )
        return report.model_dump()
    finally:
        db.close()


@celery_app.task(name="think9.train_model")
def train_think9_model_task(run_id: str, request_payload: dict) -> dict:
    db = SessionLocal()
    try:
        run = db.get(FineTuneRun, run_id)
        if run is None:
            return {"run_id": run_id, "status": "missing"}

        request = Think9TrainRequest.model_validate(request_payload)
        run.status = "running"
        db.commit()

        dataset_version = run.dataset_version or _planned_dataset_version()
        rows, manifest = build_dataset(
            db,
            holdout_fraction=request.holdout_fraction,
            min_samples=request.min_samples,
            dataset_version=dataset_version,
        )
        plan = _training_plan(manifest, request)

        export_dir = Path(__file__).resolve().parents[2] / "data" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        target = export_dir / export_filename(manifest["dataset_version"])
        target.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

        run.status = "completed" if manifest["meets_min_samples"] else "blocked"
        run.dataset_version = manifest["dataset_version"]
        run.samples = manifest["rows"]
        run.payload = {
            "request": request.model_dump(),
            "manifest": manifest,
            "plan": plan,
            "artifact_path": str(target),
        }
        run.metrics = {
            "training_rows": manifest["training_rows"],
            "holdout_rows": manifest["holdout_rows"],
            "meets_min_samples": manifest["meets_min_samples"],
        }
        db.commit()
        return {
            "run_id": run.id,
            "status": run.status,
            "dataset_version": run.dataset_version,
            "samples": run.samples,
            "artifact_path": str(target),
        }
    except Exception as exc:
        run = db.get(FineTuneRun, run_id)
        if run is not None:
            run.status = "failed"
            run.payload = {**(run.payload or {}), "error": str(exc)}
            db.commit()
        raise
    finally:
        db.close()
