"""Queries, flags, outcomes, learnings, alerts (MVP schema §7 + spec §11)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="api")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Flag(Base):
    """Contradiction / precedent flags on a brief (agentic-workflow.md §2.6)."""

    __tablename__ = "flags"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    brief_id: Mapped[str] = mapped_column(
        ForeignKey("decision_briefs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flag_type: Mapped[str] = mapped_column(String(32), nullable=False)  # contradicts|supersedes|…
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # low|medium|high
    cited_chunk: Mapped[str | None] = mapped_column(ForeignKey("chunks.id"), nullable=True)
    conflict_text: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolution_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Outcome(Base):
    __tablename__ = "outcomes"

    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), primary_key=True
    )
    result: Mapped[str] = mapped_column(String(16), nullable=False)  # success|partial|failure|superseded
    metric_deltas: Mapped[dict] = mapped_column(JSONB, default=dict)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Learning(Base):
    """Derived learning statements for contradiction checks (spec §11.3)."""

    __tablename__ = "learnings"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    decision_ref: Mapped[str | None] = mapped_column(
        ForeignKey("decisions.id", ondelete="SET NULL"), nullable=True
    )
    source_doc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("decision_briefs.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # contradiction|weak_evidence|gate
    channel: Mapped[str] = mapped_column(String(16), nullable=False)  # email|slack
    recipients: Mapped[list] = mapped_column(JSONB, default=list)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
