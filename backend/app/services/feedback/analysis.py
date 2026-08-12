"""Outcome analysis (docs/feedback-loops.md §2): accuracy by category/class,
confidence calibration buckets, precedent usefulness, and blind spots.

Only decisions with recorded outcomes are scored; coverage is always reported.
`superseded` outcomes are counted but excluded from accuracy.
"""


from sqlalchemy.orm import Session

from app.db.models import Decision, DecisionBrief, Outcome
from app.schemas.feedback import (
    BlindSpot,
    CalibrationBucket,
    CategoryAccuracy,
    OutcomeAnalysis,
    PrecedentUsefulness,
)

RESULT_WEIGHT = {"success": 1.0, "partial": 0.5, "failure": 0.0, "superseded": None}
OUTCOME_COVERAGE_FLOOR = 0.4
FAILURE_RATE_FLOOR = 0.3
PRECEDENT_USEFUL_ACCURACY = 0.7
PRECEDENT_MIN_USES = 3


def result_weight(result: str) -> float | None:
    return RESULT_WEIGHT.get(result)


def accuracy_of(outcomes: list[Outcome]) -> float:
    weights = [w for o in outcomes if (w := result_weight(o.result)) is not None]
    return round(sum(weights) / len(weights), 3) if weights else 0.0


def _accuracy_for(group: list[tuple[object, Outcome]]) -> float:
    weights = [w for _, o in group if (w := result_weight(o.result)) is not None]
    return round(sum(weights) / len(weights), 3) if weights else 0.0


class OutcomeAnalyzer:
    def __init__(self) -> None:
        self._outcomes: dict[str, Outcome] = {}

    def analyze(self, session: Session) -> OutcomeAnalysis:
        decisions = session.query(Decision).all()
        self._outcomes = {o.decision_id: o for o in session.query(Outcome).all()}
        brief_by_decision: dict[str, DecisionBrief] = {}
        for b in session.query(DecisionBrief).order_by(DecisionBrief.created_at.desc()):
            brief_by_decision.setdefault(b.decision_id, b)

        decided = [d for d in decisions if d.id in self._outcomes]
        outcome_accuracy = accuracy_of(list(self._outcomes.values()))
        analysis = OutcomeAnalysis(
            total_decisions=len(decisions),
            outcomes_recorded=len(self._outcomes),
            overall_accuracy=outcome_accuracy,
            accuracy_by_category=self._group_accuracy(decided, lambda d: d.category or "unknown"),
            accuracy_by_decision_class=self._group_accuracy(decided, lambda d: d.decision_class or "unknown"),
            calibration=self._calibration(decided, brief_by_decision),
            precedent_usefulness=self._precedents(session, decided, brief_by_decision),
            blind_spots=self._blind_spots(decisions, brief_by_decision),
        )
        buckets = analysis.calibration
        if buckets:
            total = sum(b.count for b in buckets)
            analysis.calibration_error = round(
                sum(b.count / total * abs(b.predicted_mean - b.observed_rate) for b in buckets), 3
            )
        return analysis

    def _group_accuracy(self, decided: list[Decision], key_fn) -> list[CategoryAccuracy]:
        grouped: dict[str, list[Decision]] = {}
        for d in decided:
            grouped.setdefault(key_fn(d), []).append(d)
        rows: list[CategoryAccuracy] = []
        for key, group in sorted(grouped.items()):
            weights = [
                w for d in group if (w := result_weight(self._outcomes[d.id].result)) is not None
            ]
            rows.append(
                CategoryAccuracy(
                    category=key,
                    decisions=len(group),
                    outcomes=len(group),
                    coverage=1.0,
                    accuracy=round(sum(weights) / len(weights), 3) if weights else 0.0,
                )
            )
        return rows

    def _calibration(
        self,
        decided: list[Decision],
        brief_by_decision: dict[str, DecisionBrief],
    ) -> list[CalibrationBucket]:
        buckets: dict[int, list[float]] = {}
        for d in decided:
            outcome = self._outcomes[d.id]
            if result_weight(outcome.result) is None:
                continue
            brief = brief_by_decision.get(d.id)
            if brief is None or brief.confidence is None:
                continue
            c = max(0.2, min(1.0, brief.confidence))
            idx = int((c - 0.2) // 0.1)  # 0..7
            buckets.setdefault(idx, []).append(c)

        rows: list[CalibrationBucket] = []
        for idx in range(8):
            low = round(0.2 + idx * 0.1, 2)
            high = round(0.3 + idx * 0.1, 2)
            preds = buckets.get(idx, [])
            if not preds:
                continue
            rows.append(
                CalibrationBucket(
                    bucket_low=low,
                    bucket_high=high,
                    count=len(preds),
                    predicted_mean=round(sum(preds) / len(preds), 3),
                    observed_rate=self._observed_rate_for_bucket(idx, decided, brief_by_decision),
                )
            )
        return rows

    def _observed_rate_for_bucket(
        self,
        idx: int,
        decided: list[Decision],
        brief_by_decision: dict[str, DecisionBrief],
    ) -> float:
        weights = []
        for d in decided:
            o = self._outcomes[d.id]
            w = result_weight(o.result)
            if w is None:
                continue
            brief = brief_by_decision.get(d.id)
            if brief is None or brief.confidence is None:
                continue
            c = max(0.2, min(1.0, brief.confidence))
            if int((c - 0.2) // 0.1) != idx:
                continue
            weights.append(w)
        return round(sum(weights) / len(weights), 3) if weights else 0.0

    def _precedents(
        self,
        session: Session,
        decided: list[Decision],
        brief_by_decision: dict[str, DecisionBrief],
    ) -> list[PrecedentUsefulness]:
        # per chunk: used_count across ALL briefs; weighted success across briefs
        # whose decision has an outcome
        used: dict[str, int] = {}
        weighted: dict[str, float] = {}
        outcome_uses: dict[str, int] = {}
        for brief in session.query(DecisionBrief).all():
            outcome = self._outcomes.get(brief.decision_id or "")
            for chunk_id in (brief.brief or {}).get("provenance_chunks", []):
                used[chunk_id] = used.get(chunk_id, 0) + 1
                if outcome is not None:
                    w = result_weight(outcome.result)
                    if w is not None:
                        weighted[chunk_id] = weighted.get(chunk_id, 0.0) + w
                        outcome_uses[chunk_id] = outcome_uses.get(chunk_id, 0) + 1

        rows: list[PrecedentUsefulness] = []
        for chunk_id, total in used.items():
            ou = outcome_uses.get(chunk_id, 0)
            rate = round(weighted.get(chunk_id, 0.0) / ou, 3) if ou else 0.0
            rows.append(
                PrecedentUsefulness(
                    chunk_id=chunk_id,
                    document_id=chunk_id,
                    title="",
                    used_count=total,
                    success_rate=rate,
                    useful=rate >= PRECEDENT_USEFUL_ACCURACY and total >= PRECEDENT_MIN_USES,
                )
            )
        rows.sort(key=lambda r: (r.success_rate, r.used_count), reverse=True)
        return rows[:20]

    def _blind_spots(
        self,
        decisions: list[Decision],
        brief_by_decision: dict[str, DecisionBrief],
    ) -> list[BlindSpot]:
        grouped: dict[str, list[Decision]] = {}
        for d in decisions:
            grouped.setdefault(d.category or "unknown", []).append(d)

        spots: list[BlindSpot] = []
        for category, group in grouped.items():
            with_outcome = [d for d in group if d.id in self._outcomes]
            coverage = len(with_outcome) / len(group) if group else 0.0
            failures = sum(1 for d in with_outcome if (self._outcomes[d.id].result == "failure"))
            failure_rate = failures / len(with_outcome) if with_outcome else 0.0
            reasons = []
            if coverage < OUTCOME_COVERAGE_FLOOR:
                reasons.append(f"outcome coverage {coverage:.0%} < {OUTCOME_COVERAGE_FLOOR:.0%}")
            if with_outcome and failure_rate >= FAILURE_RATE_FLOOR and len(with_outcome) >= 2:
                reasons.append(f"failure rate {failure_rate:.0%} >= {FAILURE_RATE_FLOOR:.0%}")
            if not reasons:
                continue
            spots.append(BlindSpot(category=category, reason="; ".join(reasons), failure_rate=round(failure_rate, 3), coverage=round(coverage, 3)))
        spots.sort(key=lambda s: (s.failure_rate, -s.coverage), reverse=True)
        return spots
