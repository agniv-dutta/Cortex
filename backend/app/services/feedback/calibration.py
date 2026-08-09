"""Confidence calibration (docs/feedback-loops.md §3.1).

Fits a monotone piecewise-linear map from historical (predicted confidence,
outcome) pairs; snapshots it to calibration_models (versioned, one active row per
kind); and transforms raw scores via apply(). Under-sampled buckets fall back to
the global success rate so a thin tail cannot distort the curve.
"""

import logging
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.ulid import new_id
from app.db.models import CalibrationModel, Decision, DecisionBrief, Outcome
from app.services.feedback.analysis import result_weight

logger = logging.getLogger(__name__)

KIND = "confidence"
CONFIDENCE_FLOOR = 0.2
BUCKET_WIDTH = 0.1
N_BUCKETS = 8
MIN_BUCKET_SAMPLES = 5


def _bucket_index(confidence: float) -> int:
    return int((max(CONFIDENCE_FLOOR, min(1.0, confidence)) - CONFIDENCE_FLOOR) // BUCKET_WIDTH)


def fit(pairs: list[tuple[float, str]]) -> dict:
    """pairs: (predicted_confidence, result). Returns a serializable payload."""
    scored = [(c, w) for c, result in pairs if (w := result_weight(result)) is not None]
    if not scored:
        return {"kind": KIND, "points": [], "global_success": 0.0, "samples": 0}

    global_success = round(sum(w for _, w in scored) / len(scored), 3)
    bucket_weights: dict[int, list[float]] = {}
    bucket_preds: dict[int, list[float]] = {}
    for c, w in scored:
        idx = _bucket_index(c)
        bucket_weights.setdefault(idx, []).append(w)
        bucket_preds.setdefault(idx, []).append(c)

    points: list[dict] = []
    for idx in range(N_BUCKETS):
        ws = bucket_weights.get(idx)
        if not ws:
            continue
        mid = round(CONFIDENCE_FLOOR + (idx + 0.5) * BUCKET_WIDTH, 2)
        observed = round(sum(ws) / len(ws), 3) if len(ws) >= MIN_BUCKET_SAMPLES else global_success
        points.append({"x": mid, "y": observed, "count": len(ws)})
    return {"kind": KIND, "points": sorted(points, key=lambda p: p["x"]), "global_success": global_success, "samples": len(scored)}


def apply(payload: dict, confidence: float) -> float:
    """Piecewise-linear interpolation over the fitted points; clamps to [floor, 1.0]."""
    points = payload.get("points") or []
    if not points:
        return max(CONFIDENCE_FLOOR, min(1.0, float(confidence)))
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    c = float(confidence)
    if c <= xs[0]:
        out = ys[0]
    elif c >= xs[-1]:
        out = ys[-1]
    else:
        for i in range(len(xs) - 1):
            if xs[i] <= c <= xs[i + 1]:
                span = xs[i + 1] - xs[i]
                t = (c - xs[i]) / span if span else 0.0
                out = ys[i] + t * (ys[i + 1] - ys[i])
                break
        else:  # pragma: no cover
            out = ys[-1]
    return max(CONFIDENCE_FLOOR, min(1.0, round(out, 3)))


class ConfidenceCalibrator:
    def collect(self, session: Session) -> list[tuple[float, str]]:
        brief_by_decision: dict[str, DecisionBrief] = {}
        for b in session.query(DecisionBrief).order_by(desc(DecisionBrief.created_at)):
            brief_by_decision.setdefault(b.decision_id, b)
        pairs: list[tuple[float, str]] = []
        for o in session.query(Outcome).all():
            brief = brief_by_decision.get(o.decision_id)
            if brief is None or brief.confidence is None:
                continue
            pairs.append((brief.confidence, o.result))
        return pairs

    def retrain(self, session: Session) -> tuple[dict, dict, int]:
        """Fit, persist a new active model, deactivate the old one.
        Returns (payload, metrics, version)."""
        pairs = self.collect(session)
        payload = fit(pairs)

        current = (
            session.query(CalibrationModel)
            .filter_by(kind=KIND, active=True)
            .order_by(desc(CalibrationModel.version))
            .first()
        )
        version = (current.version + 1) if current else 1

        calibration_error = self._weighted_error(payload)
        metrics = {"calibration_error": calibration_error, "samples": payload["samples"]}

        model = CalibrationModel(
            id=new_id("cal"),
            kind=KIND,
            version=version,
            active=True,
            samples=payload["samples"],
            payload=payload,
            metrics=metrics,
        )
        session.add(model)
        if current:
            current.active = False
        session.commit()
        logger.info("calibration model v%d fitted on %d samples (error=%.3f)", version, payload["samples"], calibration_error)
        return payload, metrics, version

    @staticmethod
    def load_active(session: Session) -> dict | None:
        model = (
            session.query(CalibrationModel)
            .filter_by(kind=KIND, active=True)
            .order_by(desc(CalibrationModel.version))
            .first()
        )
        return model.payload if model else None

    @staticmethod
    def _weighted_error(payload: dict) -> float:
        points = payload.get("points") or []
        total = sum(p["count"] for p in points)
        if not total:
            return 0.0
        return round(
            sum(p["count"] / total * abs(p["x"] - p["y"]) for p in points), 3
        )


def calibrated_confidence(session: Session, raw: float) -> float:
    """Apply the active calibration model if one exists; else pass through."""
    payload = ConfidenceCalibrator.load_active(session)
    return apply(payload, raw) if payload else raw


def _pending_cadence(session: Session) -> bool:
    """Cadence guard: retrain when ≥50 new outcomes since the active model."""
    active = (
        session.query(CalibrationModel)
        .filter_by(kind=KIND, active=True)
        .order_by(desc(CalibrationModel.version))
        .first()
    )
    if active is None:
        return True
    new_since = session.query(Outcome).filter(Outcome.recorded_at > active.created_at).count()
    return new_since >= 50
