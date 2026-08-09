"""Celery tasks — async decision brief generation (MVP Week 3, Slack ack→thread).

Runs outside the request cycle; opens its own DB session (engine pool shared).
"""

import logging

from app.core.database import SessionLocal
from app.services.orchestrator import DecisionOrchestrator
from app.schemas.portfolio import PortfolioIntelligenceRequest
from app.services.portfolio import PortfolioIntelligenceService

logger = logging.getLogger(__name__)

from app.workers.celery_app import celery_app  # noqa: E402


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
