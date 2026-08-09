"""Feedback-loop services (docs/feedback-loops.md): outcome analysis, confidence
calibration, precedent stats + ranking boost, fine-tune export, reporting, and
the event recorder."""

from app.services.feedback.analysis import OutcomeAnalyzer, accuracy_of, result_weight
from app.services.feedback.calibration import ConfidenceCalibrator, apply, calibrated_confidence, fit
from app.services.feedback.finetune import build_rows, export_filename
from app.services.feedback.precedent import PrecedentBoostProvider, PrecedentStatsService
from app.services.feedback.recorder import FeedbackRecorder
from app.services.feedback.reporting import ReportingService

__all__ = [
    "ConfidenceCalibrator",
    "FeedbackRecorder",
    "OutcomeAnalyzer",
    "PrecedentBoostProvider",
    "PrecedentStatsService",
    "ReportingService",
    "accuracy_of",
    "apply",
    "build_rows",
    "calibrated_confidence",
    "export_filename",
    "fit",
    "result_weight",
]
