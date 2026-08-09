"""Decisions, briefs, provenance, flags, outcomes (spec §4.2, MVP schema §7)."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

DECISION_STATUSES = {
    "draft",
    "pending_review",
    "in_approval",
    "approved",
    "rejected",
    "executed",
    "archived",
    "superseded",
}


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    decision_class: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    brands: Mapped[list] = mapped_column(JSONB, default=list)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    requester: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_due_at: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DecisionBrief(Base):
    __tablename__ = "decision_briefs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    query_id: Mapped[str | None] = mapped_column(
        ForeignKey("queries.id", ondelete="SET NULL"), nullable=True
    )
    brief: Mapped[dict] = mapped_column(JSONB, nullable=False)  # recommended_action, precedents, risks…
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    revision_round: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BriefChunk(Base):
    """Provenance: which chunks grounded a brief (spec §4.2, citation integrity)."""

    __tablename__ = "brief_chunks"

    brief_id: Mapped[str] = mapped_column(
        ForeignKey("decision_briefs.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("chunks.id"), primary_key=True
    )
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
