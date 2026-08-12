"""Decision aggregation agent - scans incoming decisions for multi-brand patterns."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ulid import new_id
from app.db.models import Decision, DecisionBrief
from app.schemas.portfolio import (
    ExecutionTrigger,
    PortfolioCluster,
    PortfolioEvidence,
    PortfolioIntelligenceResponse,
    PortfolioOpportunity,
    PortfolioRisk,
    PortfolioSummary,
)

# Signal detection patterns for decisions
DECISION_SIGNALS = {
    "vendor_negotiation": {"vendor", "supplier", "counterparty", "renegotiate", "renewal", "contract"},
    "ingredient_sourcing": {"ingredient", "formula", "premix", "raw material", "sourcing"},
    "moq_negotiation": {"moq", "minimum order quantity", "volume commitment", "bundle"},
    "pricing_pressure": {"price increase", "price hike", "discount", "volume discount"},
    "sustainability_initiative": {"sustainability", "eco", "recyclable", "green", "carbon"},
    "brand_positioning": {"positioning", "messaging", "brand voice", "campaign"},
}

CONSOLIDATION_BLADE = {"vendor", "ingredient"}
COORDINATION_THEMES = {"sustainability_initiative", "brand_positioning"}
CONCENTRATION_RISK_THRESHOLD = 5
HIGH_PRIORITY_THRESHOLD = 5
EXECUTION_SCORE_THRESHOLD = 0.6


@dataclass(slots=True)
class DecisionObservation:
    decision_id: str
    decision_class: str
    brand: str
    dimension: str
    key: str
    signal_kind: str
    evidence: str
    created_at: datetime | None
    severity: float = 0.0


@dataclass(slots=True)
class DecisionClusterAggregate:
    dimension: str
    key: str
    brands: set[str] = field(default_factory=set)
    decisions: set[str] = field(default_factory=set)
    decision_classes: Counter[str] = field(default_factory=Counter)
    signal_kinds: Counter[str] = field(default_factory=Counter)
    snippets: list[PortfolioEvidence] = field(default_factory=list)
    latest_at: datetime | None = None
    severities: list[float] = field(default_factory=list)

    def add(self, observation: DecisionObservation) -> None:
        self.brands.add(observation.brand)
        self.decisions.add(observation.decision_id)
        self.decision_classes[observation.decision_class] += 1
        self.signal_kinds[observation.signal_kind] += 1
        self.severities.append(observation.severity)
        if observation.created_at and (self.latest_at is None or observation.created_at > self.latest_at):
            self.latest_at = observation.created_at
        self.snippets.append(
            PortfolioEvidence(
                document_id=observation.decision_id,
                chunk_id=observation.decision_id,
                doc_type="decision",
                title=f"Decision: {observation.decision_class}",
                brand=observation.brand,
                snippet=observation.evidence[:240],
                signal_kind=observation.signal_kind,
            )
        )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _title_case(text: str) -> str:
    return " ".join(part.capitalize() for part in _norm(text).split())


def _extract_keywords(text: str, keyword_map: dict[str, set[str]]) -> list[str]:
    lowered = _norm(text)
    hits: list[str] = []
    for label, keywords in keyword_map.items():
        if any(keyword in lowered for keyword in keywords):
            hits.append(label)
    return hits


def _extract_named_entity(text: str, keywords: tuple[str, ...]) -> str | None:
    lowered = _norm(text)
    for keyword in keywords:
        match = re.search(rf"\b{re.escape(keyword)}\s+([A-Za-z0-9&\-][A-Za-z0-9&\-\s]{{1,48}})", lowered, flags=re.IGNORECASE)
        if match:
            return _title_case(match.group(1))
    return None


def _severity_score(signal_kind: str, evidence: str) -> float:
    base = {
        "vendor_negotiation": 0.6,
        "ingredient_sourcing": 0.5,
        "moq_negotiation": 0.5,
        "pricing_pressure": 0.6,
        "sustainability_initiative": 0.3,
        "brand_positioning": 0.35,
    }.get(signal_kind, 0.3)
    lowered = _norm(evidence)
    if any(term in lowered for term in {"critical", "urgent", "failure", "fail", "blocked", "risk"}):
        base = min(1.0, base + 0.15)
    return round(min(1.0, base), 3)


def _score_decision_cluster(agg: DecisionClusterAggregate, total_brands: int) -> float:
    import math

    brand_coverage = len(agg.brands) / max(1, total_brands)
    brand_depth = min(1.0, len(agg.brands) / 5.0)
    breadth = min(1.0, len(agg.decisions) / 4.0)
    recency = 0.5
    if agg.latest_at:
        age_days = max(0.0, (datetime.now(timezone.utc) - agg.latest_at).total_seconds() / 86400.0)
        recency = math.exp(-age_days / 90.0)  # Decisions are more time-sensitive
    class_mix = min(1.0, len(agg.decision_classes) / 3.0)
    signal_strength = min(1.0, sum(agg.signal_kinds.values()) / 4.0)
    severity = max(agg.severities) if agg.severities else 0.0
    shared_dependency_bonus = 0.20 if agg.dimension in CONSOLIDATION_BLADE else 0.12 if agg.dimension == "theme" else 0.08
    
    score = (
        0.20 * brand_coverage
        + 0.12 * brand_depth
        + 0.18 * breadth
        + 0.20 * recency
        + 0.15 * class_mix
        + 0.12 * signal_strength
        + 0.08 * severity
        + shared_dependency_bonus
    )
    return round(min(1.0, score), 3)


def _opportunity_action(dimension: str, key: str, signal_kinds: Counter[str]) -> tuple[str, str]:
    if dimension == "vendor":
        if "moq_negotiation" in signal_kinds:
            return (f"Bundle MOQ + RFQ for {key}", "procurement_queue")
        return (f"Bundle RFQ for {key}", "procurement_queue")
    if dimension == "ingredient":
        return (f"Bundle MOQ for {key}", "procurement_queue")
    if "sustainability_initiative" in signal_kinds:
        return ("Coordinate sustainability initiatives across brands", "brand_leads")
    if "brand_positioning" in signal_kinds:
        return ("Align positioning guidance across affected brands", "brand_leads")
    return (f"Coordinate cross-brand response for {key}", "portfolio_ops")


def _risk_action(dimension: str, key: str, blast_radius: int) -> tuple[str, str]:
    if dimension == "vendor":
        return (f"Assess vendor concentration risk for {key}", "procurement_leads")
    if dimension == "ingredient":
        return (f"Review ingredient concentration exposure for {key}", "supply_chain_leads")
    if blast_radius >= 5:
        return ("Escalate portfolio concentration to executive review", "executive_queue")
    return (f"Flag cross-brand exposure for {key}", "risk_ops")


def _observations_from_decision(decision: Decision) -> list[DecisionObservation]:
    observations: list[DecisionObservation] = []
    brand_values = [str(brand).strip() for brand in (decision.brands or []) if str(brand).strip() and str(brand).strip().lower() != "all"]
    if not brand_values:
        return observations

    text = f"{decision.statement} {decision.context_notes or ''} {decision.rationale or ''}"
    lowered = _norm(text)
    evidence = text.replace("\n", " ").strip()
    signal_kinds = _extract_keywords(text, DECISION_SIGNALS)

    # Extract vendors
    vendors = []
    if "vendor" in lowered or "supplier" in lowered or "counterparty" in lowered:
        extracted = _extract_named_entity(text, ("vendor", "supplier", "counterparty"))
        if extracted:
            vendors = [extracted]

    # Extract ingredients
    ingredients = []
    if "ingredient" in lowered or "formula" in lowered or "premix" in lowered:
        extracted = _extract_named_entity(text, ("ingredient", "formula", "premix", "raw material"))
        if extracted:
            ingredients = [extracted]

    # Extract themes from signal kinds
    themes = list(dict.fromkeys(signal_kinds))

    for brand in brand_values:
        for vendor in vendors:
            observations.append(
                DecisionObservation(
                    decision_id=decision.id,
                    decision_class=decision.decision_class,
                    brand=brand,
                    dimension="vendor",
                    key=_title_case(vendor),
                    signal_kind="vendor_negotiation" if "vendor_negotiation" in signal_kinds else "vendor_dependency",
                    evidence=evidence,
                    created_at=decision.created_at,
                    severity=_severity_score("vendor_negotiation" if "vendor_negotiation" in signal_kinds else "vendor_dependency", evidence),
                )
            )
        for ingredient in ingredients:
            observations.append(
                DecisionObservation(
                    decision_id=decision.id,
                    decision_class=decision.decision_class,
                    brand=brand,
                    dimension="ingredient",
                    key=_title_case(ingredient),
                    signal_kind="moq_negotiation" if "moq_negotiation" in signal_kinds else "ingredient_dependency",
                    evidence=evidence,
                    created_at=decision.created_at,
                    severity=_severity_score("moq_negotiation" if "moq_negotiation" in signal_kinds else "ingredient_dependency", evidence),
                )
            )
        for theme in themes:
            observations.append(
                DecisionObservation(
                    decision_id=decision.id,
                    decision_class=decision.decision_class,
                    brand=brand,
                    dimension="theme",
                    key=_title_case(theme),
                    signal_kind=theme,
                    evidence=evidence,
                    created_at=decision.created_at,
                    severity=_severity_score(theme, evidence),
                )
            )
    return observations


def _aggregate_decision_observations(
    observations: Iterable[DecisionObservation],
    *,
    min_brands: int,
    min_score: float,
    total_brand_count: int,
    report_type: str,
) -> PortfolioIntelligenceResponse:
    grouped: dict[tuple[str, str], DecisionClusterAggregate] = {}
    for obs in observations:
        key = (obs.dimension, obs.key)
        if key not in grouped:
            grouped[key] = DecisionClusterAggregate(dimension=obs.dimension, key=obs.key)
        grouped[key].add(obs)

    clusters: list[PortfolioCluster] = []
    opportunities: list[PortfolioOpportunity] = []
    risks: list[PortfolioRisk] = []
    triggers: list[ExecutionTrigger] = []
    estimated_value_created = 0.0

    for agg in grouped.values():
        if len(agg.brands) < min_brands:
            continue

        score = _score_decision_cluster(agg, total_brand_count)
        if score < min_score and agg.dimension not in CONSOLIDATION_BLADE:
            continue

        summary = (
            f"{agg.dimension} '{agg.key}' appears across {len(agg.brands)} brands "
            f"({len(agg.decisions)} decisions, {sum(agg.signal_kinds.values())} signals)."
        )
        drivers = [f"{kind}: {count}" for kind, count in agg.signal_kinds.most_common()]
        evidence = agg.snippets[:6]
        max_severity = max(agg.severities or [0.0])
        action, target = (
            _opportunity_action(agg.dimension, agg.key, agg.signal_kinds)
            if max_severity < 0.7
            else _risk_action(agg.dimension, agg.key, len(agg.brands))
        )

        cluster = PortfolioCluster(
            cluster_id=new_id("dclu"),
            dimension=agg.dimension,
            key=agg.key,
            title=f"Cross-brand decision cluster: {agg.key}",
            summary=summary,
            affected_brands=sorted(agg.brands),
            document_count=len(agg.decisions),
            evidence_count=sum(agg.signal_kinds.values()),
            score=score,
            drivers=drivers,
            evidence=evidence,
            recommended_action=action,
            execution_target=target,
        )
        clusters.append(cluster)

        has_shared_dependency = agg.dimension in CONSOLIDATION_BLADE
        is_coordination_theme = agg.dimension == "theme" and any(k in agg.signal_kinds for k in COORDINATION_THEMES)
        high_brand_coverage = len(agg.brands) >= HIGH_PRIORITY_THRESHOLD
        concentration_risk = has_shared_dependency and len(agg.brands) >= CONCENTRATION_RISK_THRESHOLD

        if has_shared_dependency and max_severity < 0.7 and score >= min_score:
            opportunities.append(
                PortfolioOpportunity(
                    **cluster.model_dump(),
                    opportunity_type="consolidation" if agg.dimension == "vendor" else "bundle_moq",
                )
            )
            value_multiplier = 35000.0 if agg.dimension == "vendor" else 25000.0
            estimated_value_created += score * len(agg.brands) * value_multiplier
            triggers.append(
                ExecutionTrigger(
                    trigger_id=new_id("dtrg"),
                    action="route_bundled_rfq",
                    target=target,
                    priority="high" if high_brand_coverage or score >= 0.8 else "medium",
                    reason=action,
                    linked_cluster_ids=[cluster.cluster_id],
                    should_execute=True,
                )
            )
        if is_coordination_theme and score >= min_score:
            opportunities.append(
                PortfolioOpportunity(
                    **cluster.model_dump(),
                    opportunity_type="campaign_coordination",
                )
            )
            estimated_value_created += score * len(agg.brands) * 15000.0
            triggers.append(
                ExecutionTrigger(
                    trigger_id=new_id("dtrg"),
                    action="notify_brand_leads",
                    target=target,
                    priority="high" if high_brand_coverage else "medium",
                    reason=action,
                    linked_cluster_ids=[cluster.cluster_id],
                    should_execute=True,
                )
            )

        if max_severity >= 0.7 or concentration_risk:
            blast_radius = len(agg.brands)
            risks.append(
                PortfolioRisk(
                    **cluster.model_dump(),
                    risk_type="shared_dependency_risk" if has_shared_dependency else "portfolio_trend_risk",
                    blast_radius=blast_radius,
                )
            )
            risk_action, risk_target = _risk_action(agg.dimension, agg.key, blast_radius)
            triggers.append(
                ExecutionTrigger(
                    trigger_id=new_id("dtrg"),
                    action="flag_portfolio_risk",
                    target=risk_target,
                    priority="critical" if blast_radius >= 8 else "high" if blast_radius >= 5 else "medium",
                    reason=risk_action,
                    linked_cluster_ids=[cluster.cluster_id],
                    should_execute=True,
                )
            )

    total_decisions = len({obs.decision_id for obs in observations})
    summary = PortfolioSummary(
        total_brands_scanned=total_brand_count,
        total_documents_scanned=total_decisions,
        clusters_found=len(clusters),
        opportunities_found=len(opportunities),
        risks_found=len(risks),
        triggers_fired=len(triggers),
        estimated_value_created=round(estimated_value_created, 2),
    )

    metadata = {
        "min_brands": min_brands,
        "min_score": min_score,
        "report_type": report_type,
        "cluster_keys": [f"{c.dimension}:{c.key}" for c in clusters],
        "source": "decisions",
    }
    return PortfolioIntelligenceResponse(
        report_type=report_type,  # type: ignore[arg-type]
        generated_at=datetime.now(timezone.utc),
        summary=summary,
        clusters=clusters,
        opportunities=opportunities,
        risks=risks,
        triggers=triggers,
        metadata=metadata,
    )


class DecisionAggregationService:
    """Aggregation agent that scans incoming decisions for multi-brand patterns."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def scan_decisions(
        self,
        since_days: int = 30,
        brands: list[str] | None = None,
        min_brands: int = 2,
        min_score: float = 0.6,
        report_type: str = "ad_hoc",
    ) -> PortfolioIntelligenceResponse:
        """Scan recent decisions for multi-brand patterns."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

        stmt = select(Decision).where(
            Decision.status.in_(["approved", "executed"]),
            Decision.created_at >= cutoff,
        )
        if brands:
            stmt = stmt.where(Decision.brands.op("?|")(brands))

        decisions = list(self.session.execute(stmt).scalars().all())

        observations: list[DecisionObservation] = []
        brand_universe: set[str] = set()
        for decision in decisions:
            for brand in decision.brands or []:
                brand_str = str(brand).strip()
                if brand_str and brand_str.lower() != "all":
                    brand_universe.add(brand_str)
            observations.extend(_observations_from_decision(decision))

        return _aggregate_decision_observations(
            observations,
            min_brands=min_brands,
            min_score=min_score,
            total_brand_count=len(brand_universe) or 1,
            report_type=report_type,
        )

    def generate_monthly_report(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> PortfolioIntelligenceResponse:
        """Generate monthly cross-portfolio value report."""
        if month is None:
            month = datetime.now(timezone.utc).month
        if year is None:
            year = datetime.now(timezone.utc).year

        # Calculate date range for the month
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        stmt = select(Decision).where(
            Decision.status.in_(["approved", "executed"]),
            Decision.created_at >= start_date,
            Decision.created_at < end_date,
        )

        decisions = list(self.session.execute(stmt).scalars().all())

        observations: list[DecisionObservation] = []
        brand_universe: set[str] = set()
        for decision in decisions:
            for brand in decision.brands or []:
                brand_str = str(brand).strip()
                if brand_str and brand_str.lower() != "all":
                    brand_universe.add(brand_str)
            observations.extend(_observations_from_decision(decision))

        return _aggregate_decision_observations(
            observations,
            min_brands=2,
            min_score=0.5,  # Lower threshold for monthly reports to capture more patterns
            total_brand_count=len(brand_universe) or 1,
            report_type="monthly",
        )
