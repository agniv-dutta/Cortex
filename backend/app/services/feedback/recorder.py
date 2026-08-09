"""Event recorder (docs/feedback-loops.md §1): review actions and outcomes, and
the downstream stat refreshes they trigger."""

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.ulid import new_id
from app.db.models import Decision, DecisionBrief, Outcome, ReviewEvent
from app.services.feedback.precedent import PrecedentStatsService

logger = logging.getLogger(__name__)

OUTCOME_REVIEW_MONTHS = 6


class FeedbackRecorder:
    def record_review(
        self,
        session: Session,
        decision_id: str,
        action: str,
        reviewer: str | None,
        reason: str | None,
    ) -> ReviewEvent:
        decision = session.get(Decision, decision_id)
        if decision is None:
            raise KeyError(f"decision not found: {decision_id}")

        brief = (
            session.query(DecisionBrief)
            .filter_by(decision_id=decision_id)
            .order_by(DecisionBrief.created_at.desc())
            .first()
        )
        event = ReviewEvent(
            id=new_id("rvw"),
            decision_id=decision_id,
            brief_id=brief.id if brief else None,
            action=action,
            reviewer=reviewer,
            reason=reason,
        )
        session.add(event)

        if action == "approved":
            decision.status = "approved"
            decision.decided_at = date.today()
            decision.review_due_at = date.today() + timedelta(days=OUTCOME_REVIEW_MONTHS * 30)
        elif action == "rejected":
            decision.status = "rejected"
            decision.decided_at = date.today()
        elif action == "overridden":
            decision.status = "approved"
            decision.decided_at = date.today()
            decision.review_due_at = date.today() + timedelta(days=OUTCOME_REVIEW_MONTHS * 30)

        session.commit()
        logger.info("decision %s %s by %s", decision_id, action, reviewer or "unknown")
        return event

    def record_outcome(
        self,
        session: Session,
        decision_id: str,
        result: str,
        metric_deltas: dict,
        narrative: str | None,
        recorded_by: str | None,
    ) -> Outcome:
        decision = session.get(Decision, decision_id)
        if decision is None:
            raise KeyError(f"decision not found: {decision_id}")

        outcome = Outcome(
            decision_id=decision_id,
            result=result,
            metric_deltas=metric_deltas,
            narrative=narrative,
            recorded_by=recorded_by,
        )
        session.merge(outcome)
        decision.status = "executed" if result != "failure" else "rejected"
        session.commit()

        # refresh precedent accuracy stats (feedback-loops.md §3.2 cadence)
        try:
            PrecedentStatsService.rebuild(session)
        except Exception as exc:  # pragma: no cover — stats are non-critical
            logger.warning("precedent stats refresh failed: %s", exc)
        return outcome
