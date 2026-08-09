"""Cross-portfolio aggregation, scoring, and execution triggers."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.ulid import new_id
from app.db.models import Alert, Document
from app.schemas.portfolio import (
    ExecutionTrigger,
    PortfolioCluster,
    PortfolioEvidence,
    PortfolioIntelligenceRequest,
    PortfolioIntelligenceResponse,
    PortfolioOpportunity,
    PortfolioRisk,
    PortfolioSummary,
)

COMMON_BRAND_SIGNALS = {
    "sustainability_messaging": {"sustainability", "eco", "recycl", "green"},
    "pricing_pressure": {"price increase", "price hike", "discount", "volume discount", "promo"},
    "moq_negotiation": {"moq", "minimum order quantity", "bundle", "batch", "volume commitment"},
    "supplier_issue": {"supplier issue", "supply issue", "lead time", "stockout", "capacity", "supply disruption"},
    "brand_positioning": {"positioning", "message", "messaging", "tone", "brand voice"},
}

WEATHER_RISK_TERMS = {"drought", "flood", "hurricane", "storm", "wildfire", "monsoon", "weather risk"}


@dataclass(slots=True)
class PortfolioObservation:
    document_id: str
    chunk_id: str
    doc_type: str
    title: str
    brand: str
    dimension: str
    key: str
    signal_kind: str
    evidence: str
    created_at: datetime | None
    severity: float = 0.0


@dataclass(slots=True)
class ClusterAggregate:
    dimension: str
    key: str
    brands: set[str] = field(default_factory=set)
    documents: set[str] = field(default_factory=set)
    chunks: set[str] = field(default_factory=set)
    docs_by_type: Counter[str] = field(default_factory=Counter)
    signal_kinds: Counter[str] = field(default_factory=Counter)
    snippets: list[PortfolioEvidence] = field(default_factory=list)
    latest_at: datetime | None = None
    severities: list[float] = field(default_factory=list)

    def add(self, observation: PortfolioObservation) -> None:
        self.brands.add(observation.brand)
        self.documents.add(observation.document_id)
        self.chunks.add(observation.chunk_id)
        self.docs_by_type[observation.doc_type] += 1
        self.signal_kinds[observation.signal_kind] += 1
        self.severities.append(observation.severity)
        if observation.created_at and (self.latest_at is None or observation.created_at > self.latest_at):
            self.latest_at = observation.created_at
        self.snippets.append(
            PortfolioEvidence(
                document_id=observation.document_id,
                chunk_id=observation.chunk_id,
                doc_type=observation.doc_type,
                title=observation.title,
                brand=observation.brand,
                snippet=observation.evidence[:240],
                signal_kind=observation.signal_kind,
            )
        )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _title_case(text: str) -> str:
    return " ".join(part.capitalize() for part in _norm(text).split())


def _metadata_values(metadata: dict | None, keys: Iterable[str]) -> list[str]:
    if not metadata:
        return []
    values: list[str] = []
    for key in keys:
        raw = metadata.get(key)
        if isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
        elif isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
    return values


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
        "supplier_issue": 0.8,
        "weather_risk": 0.9,
        "pricing_pressure": 0.6,
        "moq_negotiation": 0.5,
        "sustainability_messaging": 0.4,
        "brand_positioning": 0.45,
        "trend": 0.35,
    }.get(signal_kind, 0.3)
    lowered = _norm(evidence)
    if any(term in lowered for term in {"critical", "urgent", "failure", "fail", "blocked", "risk"}):
        base = min(1.0, base + 0.1)
    return round(min(1.0, base), 3)


def _score_cluster(agg: ClusterAggregate, total_brands: int) -> float:
    brand_coverage = len(agg.brands) / max(1, total_brands)
    breadth = min(1.0, len(agg.documents) / 6.0)
    recency = 0.5
    if agg.latest_at:
        age_days = max(0.0, (datetime.now(timezone.utc) - agg.latest_at).total_seconds() / 86400.0)
        recency = math.exp(-age_days / 180.0)
    type_mix = min(1.0, len(agg.docs_by_type) / 4.0)
    signal_strength = min(1.0, sum(agg.signal_kinds.values()) / 5.0)
    severity = max(agg.severities) if agg.severities else 0.0
    shared_dependency_bonus = 0.15 if agg.dimension in {"vendor", "ingredient"} else 0.08
    score = (
        0.22 * brand_coverage
        + 0.18 * breadth
        + 0.18 * recency
        + 0.17 * type_mix
        + 0.15 * signal_strength
        + 0.10 * severity
        + shared_dependency_bonus
    )
    return round(min(1.0, score), 3)


def _opportunity_action(dimension: str, key: str, signal_kinds: Counter[str]) -> tuple[str, str]:
    if dimension == "vendor":
        return (f"Bundle RFQ for {key}", "procurement_queue")
    if dimension == "ingredient":
        return (f"Bundle MOQ for {key}", "procurement_queue")
    if "sustainability_messaging" in signal_kinds:
        return ("Coordinate sustainability messaging across brands", "brand_leads")
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


def _region_risk(text: str, metadata: dict | None) -> bool:
    lowered = _norm(text)
    if any(term in lowered for term in WEATHER_RISK_TERMS):
        return True
    if metadata:
        for key in ("region", "source_region", "origin", "country"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                if value.strip().lower() in {"weather risk", "risk region"}:
                    return True
    return False


def _observations_from_document(doc: Document) -> list[PortfolioObservation]:
    observations: list[PortfolioObservation] = []
    brand_values = [str(brand).strip() for brand in (doc.brands or []) if str(brand).strip() and str(brand).strip().lower() != "all"]
    if not brand_values:
        return observations

    metadata = doc.metadata_ or {}
    vendor_values = _metadata_values(metadata, ("vendor", "vendors", "counterparty", "supplier", "suppliers"))
    ingredient_values = _metadata_values(metadata, ("ingredient", "ingredients", "formula", "premix"))
    theme_values = _metadata_values(metadata, ("theme", "themes", "topic", "topics"))

    for chunk in doc.chunks:
        text = chunk.content or ""
        lowered = _norm(text)
        evidence = text.replace("\n", " ").strip()
        signal_kinds = _extract_keywords(text, COMMON_BRAND_SIGNALS)

        if "moq" in lowered or "minimum order quantity" in lowered or "volume discount" in lowered:
            signal_kinds.append("moq_negotiation")
        if "price increase" in lowered or "discount" in lowered or "pricing" in lowered:
            signal_kinds.append("pricing_pressure")
        if any(term in lowered for term in {"sustainability", "recycl", "eco", "green"}):
            signal_kinds.append("sustainability_messaging")
        if any(term in lowered for term in {"positioning", "brand voice", "messaging", "tone"}):
            signal_kinds.append("brand_positioning")
        if any(term in lowered for term in {"supplier issue", "lead time", "stockout", "capacity", "supply disruption"}):
            signal_kinds.append("supplier_issue")
        if _region_risk(text, metadata):
            signal_kinds.append("weather_risk")

        vendors = vendor_values or []
        if not vendors:
            extracted = _extract_named_entity(text, ("vendor", "supplier", "counterparty"))
            if extracted:
                vendors = [extracted]

        ingredients = ingredient_values or []
        if not ingredients:
            extracted = _extract_named_entity(text, ("ingredient", "formula", "premix", "base"))
            if extracted:
                ingredients = [extracted]

        themes = theme_values or list(dict.fromkeys(signal_kinds))

        for brand in brand_values:
            for vendor in vendors:
                observations.append(
                    PortfolioObservation(
                        document_id=doc.id,
                        chunk_id=chunk.id,
                        doc_type=doc.doc_type,
                        title=doc.title,
                        brand=brand,
                        dimension="vendor",
                        key=_title_case(vendor),
                        signal_kind="supplier_issue" if "supplier_issue" in signal_kinds else "vendor_dependency",
                        evidence=evidence,
                        created_at=chunk.created_at or doc.created_at,
                        severity=_severity_score("supplier_issue" if "supplier_issue" in signal_kinds else "vendor_dependency", evidence),
                    )
                )
            for ingredient in ingredients:
                observations.append(
                    PortfolioObservation(
                        document_id=doc.id,
                        chunk_id=chunk.id,
                        doc_type=doc.doc_type,
                        title=doc.title,
                        brand=brand,
                        dimension="ingredient",
                        key=_title_case(ingredient),
                        signal_kind="moq_negotiation" if "moq_negotiation" in signal_kinds else "ingredient_dependency",
                        evidence=evidence,
                        created_at=chunk.created_at or doc.created_at,
                        severity=_severity_score("moq_negotiation" if "moq_negotiation" in signal_kinds else "ingredient_dependency", evidence),
                    )
                )
            for theme in themes:
                observations.append(
                    PortfolioObservation(
                        document_id=doc.id,
                        chunk_id=chunk.id,
                        doc_type=doc.doc_type,
                        title=doc.title,
                        brand=brand,
                        dimension="theme",
                        key=_title_case(theme),
                        signal_kind=theme,
                        evidence=evidence,
                        created_at=chunk.created_at or doc.created_at,
                        severity=_severity_score(theme, evidence),
                    )
                )
    return observations


def _aggregate_observations(
    observations: Iterable[PortfolioObservation],
    *,
    min_brands: int,
    min_score: float,
    total_brand_count: int,
    report_type: str,
) -> PortfolioIntelligenceResponse:
    grouped: dict[tuple[str, str], ClusterAggregate] = defaultdict(lambda: None)
    for obs in observations:
        key = (obs.dimension, obs.key)
        if grouped.get(key) is None:
            grouped[key] = ClusterAggregate(dimension=obs.dimension, key=obs.key)
        grouped[key].add(obs)

    clusters: list[PortfolioCluster] = []
    opportunities: list[PortfolioOpportunity] = []
    risks: list[PortfolioRisk] = []
    triggers: list[ExecutionTrigger] = []
    estimated_value_created = 0.0

    for agg in grouped.values():
        if agg is None or len(agg.brands) < min_brands:
            continue

        score = _score_cluster(agg, total_brand_count)
        if score < min_score and agg.dimension not in {"vendor", "ingredient"}:
            continue

        summary = (
            f"{agg.dimension} '{agg.key}' appears across {len(agg.brands)} brands "
            f"({len(agg.documents)} documents, {sum(agg.signal_kinds.values())} evidence hits)."
        )
        drivers = [f"{kind}: {count}" for kind, count in agg.signal_kinds.most_common()]
        evidence = agg.snippets[:6]
        action, target = (
            _opportunity_action(agg.dimension, agg.key, agg.signal_kinds)
            if max(agg.severities or [0.0]) < 0.7
            else _risk_action(agg.dimension, agg.key, len(agg.brands))
        )

        cluster = PortfolioCluster(
            cluster_id=new_id("clu"),
            dimension=agg.dimension,
            key=agg.key,
            title=f"Cross-brand {agg.dimension} cluster: {agg.key}",
            summary=summary,
            affected_brands=sorted(agg.brands),
            document_count=len(agg.documents),
            evidence_count=sum(agg.signal_kinds.values()),
            score=score,
            drivers=drivers,
            evidence=evidence,
            recommended_action=action,
            execution_target=target,
        )
        clusters.append(cluster)

        max_severity = max(agg.severities or [0.0])
        if agg.dimension in {"vendor", "ingredient"} and max_severity < 0.7 and score >= min_score:
            opportunities.append(
                PortfolioOpportunity(
                    **cluster.model_dump(),
                    opportunity_type="consolidation" if agg.dimension == "vendor" else "bundle_moq",
                )
            )
            estimated_value_created += score * len(agg.brands) * 25000.0
            triggers.append(
                ExecutionTrigger(
                    trigger_id=new_id("trg"),
                    action="route_bundled_rfq",
                    target=target,
                    priority="high" if len(agg.brands) >= 5 else "medium",
                    reason=action,
                    linked_cluster_ids=[cluster.cluster_id],
                    should_execute=True,
                )
            )
        elif agg.dimension == "theme" and any(k in agg.signal_kinds for k in {"sustainability_messaging", "brand_positioning"}) and score >= min_score:
            opportunities.append(
                PortfolioOpportunity(
                    **cluster.model_dump(),
                    opportunity_type="campaign_coordination",
                )
            )
            estimated_value_created += score * len(agg.brands) * 12000.0
            triggers.append(
                ExecutionTrigger(
                    trigger_id=new_id("trg"),
                    action="notify_brand_leads",
                    target=target,
                    priority="medium",
                    reason=action,
                    linked_cluster_ids=[cluster.cluster_id],
                    should_execute=True,
                )
            )

        if max_severity >= 0.7 or "weather_risk" in agg.signal_kinds:
            blast_radius = len(agg.brands)
            risks.append(
                PortfolioRisk(
                    **cluster.model_dump(),
                    risk_type="shared_dependency_risk" if agg.dimension in {"vendor", "ingredient"} else "portfolio_trend_risk",
                    blast_radius=blast_radius,
                )
            )
            risk_action, risk_target = _risk_action(agg.dimension, agg.key, blast_radius)
            triggers.append(
                ExecutionTrigger(
                    trigger_id=new_id("trg"),
                    action="flag_portfolio_risk",
                    target=risk_target,
                    priority="high" if blast_radius >= 5 else "medium",
                    reason=risk_action,
                    linked_cluster_ids=[cluster.cluster_id],
                    should_execute=True,
                )
            )

    total_documents = len({obs.document_id for obs in observations})
    summary = PortfolioSummary(
        total_brands_scanned=total_brand_count,
        total_documents_scanned=total_documents,
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


class PortfolioIntelligenceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def generate_report(self, request: PortfolioIntelligenceRequest) -> PortfolioIntelligenceResponse:
        cutoff = datetime.now(timezone.utc) - timedelta(days=request.since_days)

        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.status == "active")
            .where(Document.created_at >= cutoff)
        )
        if request.brands:
            stmt = stmt.where(Document.brands.op("?|")(request.brands))

        docs = list(self.session.execute(stmt).scalars().unique())

        observations: list[PortfolioObservation] = []
        brand_universe: set[str] = set()
        for doc in docs:
            for brand in doc.brands or []:
                brand_str = str(brand).strip()
                if brand_str and brand_str.lower() != "all":
                    brand_universe.add(brand_str)
            observations.extend(_observations_from_document(doc))

        report = _aggregate_observations(
            observations,
            min_brands=request.min_brands,
            min_score=request.min_score,
            total_brand_count=len(brand_universe) or 1,
            report_type=request.report_type,
        )

        if request.persist_alerts:
            self._persist_alerts(report)
            self.session.commit()

        return report

    def _persist_alerts(self, report: PortfolioIntelligenceResponse) -> None:
        for trigger in report.triggers:
            self.session.add(
                Alert(
                    id=new_id("alt"),
                    brief_id=None,
                    kind=f"portfolio_{trigger.action}",
                    channel="slack",
                    recipients=[
                        {
                            "target": trigger.target,
                            "priority": trigger.priority,
                            "reason": trigger.reason,
                            "cluster_ids": trigger.linked_cluster_ids,
                        }
                    ],
                )
            )

