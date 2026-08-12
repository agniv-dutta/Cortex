"""Decision-derived playbook generation.

Playbooks are refreshed from approved decisions once a category has enough
evidence. The output is intentionally deterministic so the frontend can show a
live, evidence-based view without waiting on an offline batch job.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Decision, DecisionBrief, Flag, Outcome
from app.schemas.playbook import (
    DerivedPlaybookResponse,
    PlaybookSection,
    PlaybookSubSection,
)

CATEGORY_TITLES = {
    "Vendor Management": "Vendor Negotiation Best Practices (Evidence-based)",
    "Brand Strategy": "Brand Strategy Best Practices (Evidence-based)",
    "Product Development": "Product Development Best Practices (Evidence-based)",
    "Operations": "Operations Best Practices (Evidence-based)",
}

CATEGORY_RULES: dict[str, list[tuple[str, list[str]]]] = {
    "Vendor Management": [
        ("Negotiate payment terms before price concessions", ["payment", "terms", "net", "price", "cash", "discount"]),
        ("Protect QA, audit, and certification requirements", ["qa", "quality", "audit", "certification", "compliance", "iso"]),
        ("Keep backup suppliers for volatile lanes", ["backup", "secondary", "dual", "weather", "capacity", "redundancy"]),
        ("Use MOQs as a negotiation lever, not a fixed constraint", ["moq", "minimum", "order", "volume", "forecast"]),
        ("Bind SLAs to measurable service metrics", ["sla", "penalty", "service", "metric", "late", "delay"]),
    ],
    "Brand Strategy": [
        ("Defend brand voice before making visual changes", ["voice", "tone", "visual", "identity", "positioning"]),
        ("Tie budget shifts to measurable performance signals", ["budget", "reallocation", "performance", "cac", "pipeline", "roi"]),
        ("Keep positioning language consistent across brands", ["brand", "positioning", "messaging", "narrative", "consistency"]),
        ("Test market moves against audience and channel fit", ["market", "audience", "channel", "segment", "launch"]),
    ],
    "Product Development": [
        ("Prioritize changes with clear QA gates", ["qa", "testing", "gate", "release", "validation"]),
        ("Avoid roadmap changes that create unsupported complexity", ["complexity", "scope", "integration", "technical debt"]),
        ("Use telemetry and evidence to validate feature value", ["telemetry", "metrics", "usage", "adoption", "data"]),
        ("Ship in smaller steps when risk is unclear", ["phased", "rollout", "pilot", "incremental"]),
    ],
    "Operations": [
        ("Protect uptime with explicit dispatch and buffer rules", ["uptime", "dispatch", "buffer", "inventory", "lead time"]),
        ("Escalate capacity issues before service failures spread", ["capacity", "backlog", "delay", "service"]),
        ("Tie logistics changes to measurable service impact", ["logistics", "delivery", "sla", "service", "routing"]),
        ("Hold a safety buffer for critical workflows", ["safety", "buffer", "stock", "inventory", "contingency"]),
    ],
}

POSITIVE_RESULTS = {"success", "partial"}
DECISION_STATUSES = {"approved", "executed"}
MIN_EVIDENCE = 10


@dataclass(frozen=True)
class DecisionEvidence:
    decision_id: str
    title: str
    category: str
    brands: list[str]
    updated_at: datetime
    result: str
    statement: str
    narrative: str | None
    metric_deltas: dict
    contradictions: list[str]


def _humanize_age(updated_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    delta_days = max(0, (now.date() - updated_at.date()).days)
    if delta_days == 0:
        return "Today"
    if delta_days == 1:
        return "1 day ago"
    if delta_days < 7:
        return f"{delta_days} days ago"
    if delta_days < 30:
        weeks = max(1, round(delta_days / 7))
        return "1 week ago" if weeks == 1 else f"{weeks} weeks ago"
    months = max(1, round(delta_days / 30))
    return "1 month ago" if months == 1 else f"{months} months ago"


def _normalized_text(*parts: object) -> str:
    text = " ".join(str(part) for part in parts if part)
    return re.sub(r"\s+", " ", text).lower()


def _rule_match_score(evidence: DecisionEvidence, keywords: list[str]) -> int:
    haystack = _normalized_text(
        evidence.title,
        evidence.statement,
        evidence.narrative,
        evidence.metric_deltas,
        " ".join(evidence.contradictions),
    )
    return sum(1 for keyword in keywords if keyword in haystack)


def _top_brands(evidence: list[DecisionEvidence]) -> list[str]:
    counts: Counter[str] = Counter()
    for row in evidence:
        counts.update(row.brands or [])
    top = [brand for brand, _count in counts.most_common(4) if brand and brand.lower() != "all brands"]
    return top or ["All Brands"]


def _extract_tags(category: str, evidence: list[DecisionEvidence], matched_rules: list[tuple[str, int, int]]) -> list[str]:
    counts: Counter[str] = Counter()
    for row in evidence:
        counts.update(token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", _normalized_text(row.statement, row.narrative)) if token not in {category.lower()})
    tags = [category, "Auto-updated", "Evidence-based"]
    for rule_text, _support, _positive in matched_rules[:2]:
        tags.append(rule_text.split(" ")[0])
    for token, _count in counts.most_common(2):
        tags.append(token.title())
    return list(dict.fromkeys(tags))


def _build_sections(category: str, evidence: list[DecisionEvidence], matched_rules: list[tuple[str, int, int]], contradictions: list[DecisionEvidence]) -> list[PlaybookSection]:
    total = len(evidence)

    best_practices = [
        PlaybookSubSection(
            title=rule_text,
            content=(
                f"Supported by {support} decisions, with {rule_positive} positive outcomes "
                f"across {total} approved decisions."
            ),
        )
        for rule_text, support, rule_positive in matched_rules[:4]
        if support > 0
    ]
    if not best_practices:
        best_practices = [
            PlaybookSubSection(
                title="Evidence-based pattern",
                content=f"{category} playbooks need more signal before becoming prescriptive. The current corpus is too thin.",
            )
        ]

    recent_signals = sorted(evidence, key=lambda row: row.updated_at, reverse=True)[:3]
    signal_lines = [
        f"{row.title} ({row.result})"
        for row in recent_signals
    ]

    contradiction_sections = [
        PlaybookSubSection(
            title=row.title,
            content=row.contradictions[0] if row.contradictions else "Review the associated brief for contradiction details.",
        )
        for row in contradictions[:3]
    ]
    if not contradiction_sections:
        contradiction_sections = [
            PlaybookSubSection(
                title="No active contradictions",
                content="No unresolved high-severity contradictions are currently linked to this playbook category.",
            )
        ]

    return [
        PlaybookSection(
            id=f"{category.lower().replace(' ', '-')}-best-practices",
            title=f"{category} Best Practices",
            content="Evidence extracted from approved decisions in this category.",
            subsections=best_practices,
        ),
        PlaybookSection(
            id=f"{category.lower().replace(' ', '-')}-decision-signals",
            title="Decision Signals",
            content="The most recent approved decisions reinforce these operating signals.",
            subsections=[
                PlaybookSubSection(
                    title="Recent approvals",
                    content="; ".join(signal_lines) if signal_lines else "No recent approvals yet.",
                )
            ],
        ),
        PlaybookSection(
            id=f"{category.lower().replace(' ', '-')}-contradiction-watch",
            title="Contradiction Watch",
            content="New decisions that conflict with this playbook should surface for Brand Lead review.",
            subsections=contradiction_sections,
        ),
    ]


def _collect_evidence(session: Session, category: str) -> list[DecisionEvidence]:
    rows = (
        session.query(Decision, Outcome)
        .join(Outcome, Outcome.decision_id == Decision.id)
        .filter(Decision.category == category)
        .filter(Decision.status.in_(DECISION_STATUSES))
        .order_by(Decision.updated_at.desc())
        .all()
    )

    evidence: list[DecisionEvidence] = []
    for decision, outcome in rows:
        brief = (
            session.query(DecisionBrief)
            .filter_by(decision_id=decision.id)
            .order_by(DecisionBrief.created_at.desc())
            .first()
        )
        contradictions: list[str] = []
        if brief is not None:
            flags = session.query(Flag).filter_by(brief_id=brief.id).all()
            for flag in flags:
                if flag.severity in {"high", "critical"}:
                    contradictions.append(flag.conflict_text)
        evidence.append(
            DecisionEvidence(
                decision_id=decision.id,
                title=decision.statement,
                category=decision.category,
                brands=list(decision.brands or []),
                updated_at=outcome.recorded_at or decision.updated_at,
                result=outcome.result,
                statement=decision.statement,
                narrative=outcome.narrative,
                metric_deltas=outcome.metric_deltas or {},
                contradictions=contradictions,
            )
        )
    return evidence


def derive_playbook(session: Session, category: str) -> DerivedPlaybookResponse | None:
    evidence = _collect_evidence(session, category)
    if len(evidence) < MIN_EVIDENCE:
        return None

    matched_rules: list[tuple[str, int, int]] = []
    rules = CATEGORY_RULES.get(category, [])
    for rule_text, keywords in rules:
        support = sum(1 for row in evidence if _rule_match_score(row, keywords) > 0)
        positive = sum(1 for row in evidence if _rule_match_score(row, keywords) > 0 and row.result in POSITIVE_RESULTS)
        matched_rules.append((rule_text, support, positive))

    contradiction_rows = [row for row in evidence if row.contradictions]
    last_updated = max(row.updated_at for row in evidence)
    decision_ids = [row.decision_id for row in evidence]
    digest = hashlib.sha1("|".join(sorted(decision_ids)).encode("utf-8")).hexdigest()[:10]

    contradiction_count = sum(len(row.contradictions) for row in contradiction_rows)
    review_status = "needs_review" if contradiction_count else "approved"

    return DerivedPlaybookResponse(
        id=f"auto-{category.lower().replace(' ', '-')}-{digest}",
        title=CATEGORY_TITLES.get(category, f"{category} Best Practices (Evidence-based)"),
        description=(
            f"Auto-generated from {len(evidence)} approved decisions and refreshed whenever new decisions land in {category}."
        ),
        category=category,
        brands=_top_brands(evidence),
        lastUpdated=_humanize_age(last_updated),
        tags=_extract_tags(category, evidence, matched_rules),
        sections=_build_sections(category, evidence, matched_rules, contradiction_rows),
        autoGenerated=True,
        evidenceCount=len(evidence),
        contradictionCount=contradiction_count,
        reviewStatus=review_status,
        generatedFromDecisionIds=decision_ids[:20],
        source="approved decisions + outcome tracking",
    )


def derive_playbooks(session: Session, category: str | None = None) -> list[DerivedPlaybookResponse]:
    categories = [category] if category else list(CATEGORY_TITLES.keys())
    out: list[DerivedPlaybookResponse] = []
    for cat in categories:
        playbook = derive_playbook(session, cat)
        if playbook is not None:
            out.append(playbook)
    return out
