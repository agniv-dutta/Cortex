from datetime import datetime, timezone

from app.services.portfolio import PortfolioObservation, _aggregate_observations


def _obs(
    *,
    brand: str,
    dimension: str,
    key: str,
    signal_kind: str,
    evidence: str,
    doc_id: str,
    chunk_id: str,
    severity: float,
    doc_type: str = "decision",
):
    return PortfolioObservation(
        document_id=doc_id,
        chunk_id=chunk_id,
        doc_type=doc_type,
        title=f"{brand} {key}",
        brand=brand,
        dimension=dimension,
        key=key,
        signal_kind=signal_kind,
        evidence=evidence,
        created_at=datetime.now(timezone.utc),
        severity=severity,
    )


def test_bundle_moq_opportunity_is_triggered():
    observations = [
        _obs(brand="Brand A", dimension="ingredient", key="Pasta", signal_kind="moq_negotiation", evidence="Brands A and B are negotiating pasta ingredients and volume discounts", doc_id="d1", chunk_id="c1", severity=0.5),
        _obs(brand="Brand B", dimension="ingredient", key="Pasta", signal_kind="moq_negotiation", evidence="Brands A and B are negotiating pasta ingredients and volume discounts", doc_id="d2", chunk_id="c2", severity=0.5),
        _obs(brand="Brand C", dimension="ingredient", key="Pasta", signal_kind="moq_negotiation", evidence="Brands A and B are negotiating pasta ingredients and volume discounts", doc_id="d3", chunk_id="c3", severity=0.5),
    ]

    report = _aggregate_observations(
        observations,
        min_brands=3,
        min_score=0.6,
        total_brand_count=5,
        report_type="monthly",
    )

    assert report.opportunities
    assert report.triggers
    assert report.opportunities[0].execution_target == "procurement_queue"
    assert "Bundle MOQ" in report.opportunities[0].recommended_action


def test_vendor_concentration_becomes_risk():
    observations = [
        _obs(brand=f"Brand {i}", dimension="vendor", key="Vendor X", signal_kind="supplier_issue", evidence="Vendor X supplies eight brands and failure would cascade", doc_id=f"d{i}", chunk_id=f"c{i}", severity=0.9)
        for i in range(1, 9)
    ]

    report = _aggregate_observations(
        observations,
        min_brands=3,
        min_score=0.6,
        total_brand_count=10,
        report_type="monthly",
    )

    assert report.risks
    assert report.risks[0].blast_radius == 8
    assert any(trigger.action == "flag_portfolio_risk" for trigger in report.triggers)


def test_sustainability_theme_routes_to_brand_leads():
    observations = [
        _obs(brand=f"Brand {i}", dimension="theme", key="Sustainability Messaging", signal_kind="sustainability_messaging", evidence="All brands are shifting to sustainability messaging", doc_id=f"s{i}", chunk_id=f"sc{i}", severity=0.4, doc_type="playbook")
        for i in range(1, 6)
    ]

    report = _aggregate_observations(
        observations,
        min_brands=3,
        min_score=0.6,
        total_brand_count=6,
        report_type="monthly",
    )

    assert report.opportunities
    assert report.opportunities[0].execution_target == "brand_leads"
    assert any(trigger.target == "brand_leads" for trigger in report.triggers)

