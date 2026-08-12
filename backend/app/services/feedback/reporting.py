"""Dashboard + monthly report (docs/feedback-loops.md §4)."""

from collections import defaultdict
from datetime import date, datetime
from statistics import mean

from sqlalchemy.orm import Session

from app.db.models import Decision, Outcome
from app.db.models.feedback import FineTuneRun
from app.schemas.feedback import (
    DashboardMetrics,
    EmergingPattern,
    MonthlyPoint,
    MonthlyReport,
    ModelDriftReport,
    TopDecision,
)
from app.services.feedback.analysis import OutcomeAnalyzer, result_weight


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _point_series(rows: list[tuple[str, float]]) -> list[MonthlyPoint]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for month, value in rows:
        grouped[month].append(value)
    return [MonthlyPoint(month=month, value=round(mean(values), 3)) for month, values in sorted(grouped.items()) if values]


def _run_metric(run: FineTuneRun, path: tuple[str, ...], default: float = 0.0) -> float:
    value: object = run.metrics or {}
    for key in path:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _latest_payload(run: FineTuneRun | None) -> dict:
    if run is None:
        return {}
    return {
        "id": run.id,
        "kind": run.kind,
        "status": run.status,
        "dataset_version": run.dataset_version,
        "samples": run.samples,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "payload": run.payload or {},
        "metrics": run.metrics or {},
    }


def _model_drift(runs: list[FineTuneRun]) -> ModelDriftReport:
    eval_runs = [run for run in runs if run.kind == "eval" and run.created_at is not None]
    if not eval_runs:
        return ModelDriftReport()

    win_rate_rows = []
    match_delta_rows = []
    confidence_mae_delta_rows = []
    citation_overlap_delta_rows = []
    format_compliance_delta_rows = []
    for run in eval_runs:
        month = _month_key(run.created_at)
        win_rate_rows.append((month, _run_metric(run, ("comparison", "win_rate"))))
        match_delta_rows.append((month, _run_metric(run, ("comparison", "match_delta"))))
        confidence_mae_delta_rows.append((month, _run_metric(run, ("comparison", "confidence_mae_delta"))))
        citation_overlap_delta_rows.append((month, _run_metric(run, ("comparison", "citation_overlap_delta"))))
        format_compliance_delta_rows.append((month, _run_metric(run, ("comparison", "format_compliance_delta"))))

    latest_eval = max(eval_runs, key=lambda run: run.created_at or datetime.min)
    latest_train = max((run for run in runs if run.kind == "train" and run.created_at is not None), default=None, key=lambda run: run.created_at or datetime.min)
    latest_deploy = max((run for run in runs if run.kind == "deploy" and run.created_at is not None), default=None, key=lambda run: run.created_at or datetime.min)

    return ModelDriftReport(
        win_rate=_point_series(win_rate_rows),
        match_delta=_point_series(match_delta_rows),
        confidence_mae_delta=_point_series(confidence_mae_delta_rows),
        citation_overlap_delta=_point_series(citation_overlap_delta_rows),
        format_compliance_delta=_point_series(format_compliance_delta_rows),
        runs_recorded=len(runs),
        latest_eval=_latest_payload(latest_eval),
        latest_train=_latest_payload(latest_train),
        latest_deploy=_latest_payload(latest_deploy),
    )


class ReportingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.analyzer = OutcomeAnalyzer()

    def dashboard(self) -> DashboardMetrics:
        analysis = self.analyzer.analyze(self.session)
        today = date.today()
        cutoff = today.replace(day=1)

        # 3-month velocity + accuracy trend
        velocity: dict[str, int] = defaultdict(int)
        accuracy_weights: dict[str, list[float]] = defaultdict(list)
        outcomes = {o.decision_id: o for o in self.session.query(Outcome).all()}
        for d in self.session.query(Decision).all():
            if d.created_at.date() < cutoff:
                continue
            key = _month_key(d.created_at)
            velocity[key] += 1
            o = outcomes.get(d.id)
            if o is not None:
                w = result_weight(o.result)
                if w is not None:
                    accuracy_weights[key].append(w)

        velocity_series = [
            MonthlyPoint(month=m, value=velocity[m])
            for m in sorted(velocity)
        ]
        accuracy_series = [
            MonthlyPoint(month=m, value=round(sum(ws) / len(ws), 3))
            for m, ws in sorted(accuracy_weights.items()) if ws
        ]

        cost_savings = sum(
            float((o.metric_deltas or {}).get("savings_usd", 0.0) or 0.0)
            for o in outcomes.values()
        )

        due = (
            self.session.query(Decision)
            .filter(Decision.review_due_at <= today)
            .count()
        )
        outcomes_recorded = len(outcomes)
        due = max(0, due - outcomes_recorded) if outcomes_recorded else due

        return DashboardMetrics(
            decision_velocity=velocity_series,
            accuracy_trend=accuracy_series,
            cost_savings_usd=round(cost_savings, 2),
            outcomes_due=due,
            top_categories=sorted(analysis.accuracy_by_category, key=lambda c: c.accuracy, reverse=True)[:5],
            calibration_error=analysis.calibration_error,
        )

    def monthly_report(self, month: str | None = None) -> MonthlyReport:
        month = month or date.today().strftime("%Y-%m")
        analysis = self.analyzer.analyze(self.session)
        outcomes = self.session.query(Outcome).all()
        model_runs = (
            self.session.query(FineTuneRun)
            .filter(FineTuneRun.role == "decision_brief")
            .all()
        )

        # top decisions by absolute metric impact in the month
        top: list[TopDecision] = []
        for o in outcomes:
            if o.recorded_at.strftime("%Y-%m") != month:
                continue
            d = self.session.get(Decision, o.decision_id)
            if d is None:
                continue
            deltas = o.metric_deltas or {}
            impact = float(deltas.get("savings_usd", 0.0) or 0.0) + float(deltas.get("cost_usd", 0.0) or 0.0)
            top.append(
                TopDecision(
                    decision_id=d.id,
                    statement=d.statement,
                    category=d.category or "",
                    outcome=o.result,
                    impact_usd=round(abs(impact), 2),
                )
            )
        top.sort(key=lambda t: t.impact_usd, reverse=True)

        patterns = self._emerging_patterns(analysis)

        return MonthlyReport(
            month=month,
            top_decisions=top[:10],
            emerging_patterns=patterns,
            blind_spots=analysis.blind_spots,
            accuracy_summary={
                "overall": analysis.overall_accuracy,
                "outcomes": analysis.outcomes_recorded,
                "calibration_error": analysis.calibration_error,
            },
            model_drift=_model_drift(model_runs),
        )

    def _emerging_patterns(self, analysis) -> list[EmergingPattern]:
        patterns: list[EmergingPattern] = []
        for cat in analysis.accuracy_by_category:
            if cat.decisions >= 3:
                patterns.append(
                    EmergingPattern(
                        pattern=f"{cat.category} decisions measuring at {cat.accuracy:.0%} accuracy",
                        evidence=f"{cat.decisions} decisions with outcomes",
                        direction="strong" if cat.accuracy >= 0.7 else "needs attention",
                    )
                )
        for spot in analysis.blind_spots:
            patterns.append(
                EmergingPattern(
                    pattern=f"{spot.category} is an under-measured area",
                    evidence=spot.reason,
                    direction="blind spot",
                )
            )
        return patterns
