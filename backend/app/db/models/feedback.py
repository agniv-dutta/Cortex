"""Feedback-loop tables (docs/feedback-loops.md §1): review events, precedent
accuracy stats, and versioned calibration models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

REVIEW_ACTIONS = {"approved", "rejected", "deferred", "overridden"}


class ReviewEvent(Base):
    """Who approved/rejected/overrode a recommendation, and why (feedback-loops.md §1)."""

    __tablename__ = "review_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_briefs.id", ondelete="CASCADE"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # approved|rejected|deferred|overridden
    reviewer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrecedentStat(Base):
    """Per-chunk accuracy derived from how past briefs used each chunk and how
    those decisions turned out (feedback-loops.md §3.2). Feeds the ranking boost."""

    __tablename__ = "precedent_stats"

    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CalibrationModel(Base):
    """Versioned model snapshots (confidence calibration, ranking factors).
    Exactly one active row per kind."""

    __tablename__ = "calibration_models"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # confidence|ranking
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    samples: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FineTuneRun(Base):
    """Audit trail for dataset exports, eval runs, and deployment snapshots."""

    __tablename__ = "fine_tune_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # export|eval|deploy
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    dataset_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    samples: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Think9Model(Base):
    """Registry row for the active Think9 brief model."""

    __tablename__ = "think9_models"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dataset_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    samples: Mapped[int] = mapped_column(Integer, default=0)
    train_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    eval_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
