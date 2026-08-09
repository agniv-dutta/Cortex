"""Celery tasks — async decision brief generation (MVP Week 3, Slack ack→thread).

Runs outside the request cycle; opens its own DB session (engine pool shared).
"""

import logging

from app.core.database import SessionLocal
from app.services.orchestrator import DecisionOrchestrator

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
