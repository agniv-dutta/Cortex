"""Precedent accuracy stats + retrieval boost (docs/feedback-loops.md §3.2).

PrecedentStat is rebuilt from brief_chunks × decisions × outcomes:
- used_count: total briefs that cited the chunk
- accuracy: weighted success rate across briefs whose decision has an outcome

The boost provider converts accuracy into a ranking factor for decision chunks
with proven-good outcomes (strictly non-negative, so unproven chunks are never
penalized).
"""

import logging

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import BriefChunk, DecisionBrief, Outcome, PrecedentStat
from app.services.feedback.analysis import result_weight

logger = logging.getLogger(__name__)


class PrecedentStatsService:
    @staticmethod
    def rebuild(session: Session) -> int:
        outcomes = {o.decision_id: o for o in session.query(Outcome).all()}
        brief_chunks = session.query(BriefChunk).all()
        brief_ids = {bc.brief_id for bc in brief_chunks}
        briefs = {
            b.id: b
            for b in session.query(DecisionBrief).filter(DecisionBrief.id.in_(brief_ids)).all()
        }

        used: dict[str, int] = {}
        weighted: dict[str, float] = {}
        success_uses: dict[str, int] = {}
        outcome_uses: dict[str, int] = {}

        for bc in brief_chunks:
            used[bc.chunk_id] = used.get(bc.chunk_id, 0) + 1
            brief = briefs.get(bc.brief_id)
            outcome = outcomes.get(brief.decision_id) if brief and brief.decision_id else None
            if outcome is None:
                continue
            w = result_weight(outcome.result)
            if w is None:
                continue
            weighted[bc.chunk_id] = weighted.get(bc.chunk_id, 0.0) + w
            success_uses[bc.chunk_id] = success_uses.get(bc.chunk_id, 0) + (1 if w > 0 else 0)
            outcome_uses[bc.chunk_id] = outcome_uses.get(bc.chunk_id, 0) + 1

        session.query(PrecedentStat).delete()
        rows = []
        for chunk_id, total in used.items():
            ou = outcome_uses.get(chunk_id, 0)
            accuracy = round(weighted.get(chunk_id, 0.0) / ou, 3) if ou else 0.0
            su = success_uses.get(chunk_id, 0)
            rows.append(
                PrecedentStat(
                    chunk_id=chunk_id,
                    used_count=total,
                    success_count=su,
                    failure_count=ou - su,
                    accuracy=accuracy,
                )
            )
        session.add_all(rows)
        session.commit()
        logger.info("rebuilt precedent stats for %d chunks", len(rows))
        return len(rows)


class PrecedentBoostProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def boosts_for(self, session: Session, chunk_ids: list[str]) -> dict[str, float]:
        if not chunk_ids:
            return {}
        rows = (
            session.query(PrecedentStat)
            .filter(PrecedentStat.chunk_id.in_(chunk_ids))
            .filter(PrecedentStat.used_count >= self.settings.precedent_min_uses)
            .all()
        )
        boosts: dict[str, float] = {}
        for row in rows:
            boosts[row.chunk_id] = boost_value(
                row.accuracy,
                row.used_count,
                max_boost=self.settings.precedent_boost_max,
                min_accuracy=self.settings.precedent_min_accuracy,
                min_uses=self.settings.precedent_min_uses,
            )
        return boosts


def boost_value(
    accuracy: float,
    used_count: int,
    *,
    max_boost: float = 0.15,
    min_accuracy: float = 0.6,
    min_uses: int = 3,
) -> float:
    """Non-negative ranking boost for proven-accurate precedent chunks
    (feedback-loops.md §3.2). Zero for unproven or under-sampled chunks."""
    if used_count < min_uses or accuracy < min_accuracy:
        return 0.0
    return round(max_boost * (accuracy - min_accuracy) / (1.0 - min_accuracy), 4)
