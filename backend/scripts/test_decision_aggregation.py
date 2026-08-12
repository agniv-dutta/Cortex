"""Test script for decision aggregation - multi-brand pattern detection.

This script demonstrates the Phase 4 enhancement:
- Detects multi-brand patterns in decisions
- Flags consolidation opportunities (bundled RFQs, MOQ)
- Identifies concentration risks
- Generates monthly cross-portfolio value reports

Example patterns detected:
- "Brands A, B, C all negotiating pasta ingredients in Q3 → bundle MOQ, 20% discount"
- "8 brands depend on Vendor X → if they fail, portfolio is exposed → diversify"
- "All 5 home care brands pivoting to sustainability → coordinate messaging"
"""

from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.core.ulid import new_id
from app.db.models import Decision
from app.services.decision_aggregation import DecisionAggregationService


def seed_sample_decisions():
    """Seed sample decisions representing multi-brand patterns."""
    db = SessionLocal()
    
    # Pattern 1: Multiple brands negotiating with same vendor (Vendor X)
    vendor_decisions = [
        Decision(
            id=new_id("dec"),
            statement="Renegotiate contract with Vendor X for packaging materials",
            category="procurement",
            decision_class="vendor_selection",
            status="approved",
            brands=["Brand A", "Brand B", "Brand C"],
            context_notes="Vendor X proposed 8% price increase, need to negotiate better terms",
            requester="procurement_lead@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=15),
        ),
        Decision(
            id=new_id("dec"),
            statement="Evaluate alternative suppliers to Vendor X for raw materials",
            category="procurement",
            decision_class="vendor_selection",
            status="approved",
            brands=["Brand D", "Brand E"],
            context_notes="Vendor X lead times have increased, need backup options",
            requester="supply_chain@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        ),
        Decision(
            id=new_id("dec"),
            statement="Approve Vendor X renewal for Q3 with volume commitment",
            category="procurement",
            decision_class="contract",
            status="executed",
            brands=["Brand F", "Brand G"],
            context_notes="Negotiated 15% discount with 50k unit MOQ",
            requester="procurement_lead@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        ),
    ]
    
    # Pattern 2: Multiple brands using same ingredient (pasta ingredients)
    ingredient_decisions = [
        Decision(
            id=new_id("dec"),
            statement="Source durum wheat from Ingredient Supplier Y for pasta line",
            category="procurement",
            decision_class="vendor_selection",
            status="approved",
            brands=["Brand A", "Brand B"],
            context_notes="Need to secure Q3 supply, considering bulk purchase",
            requester="procurement@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=20),
        ),
        Decision(
            id=new_id("dec"),
            statement="Bundle MOQ for semolina with Ingredient Supplier Y",
            category="procurement",
            decision_class="contract",
            status="approved",
            brands=["Brand C", "Brand D", "Brand E"],
            context_notes="Coordinating across brands to achieve 100k unit threshold for 20% discount",
            requester="procurement_lead@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=12),
        ),
    ]
    
    # Pattern 3: Sustainability messaging coordination
    sustainability_decisions = [
        Decision(
            id=new_id("dec"),
            statement="Adopt eco-friendly packaging for all product lines",
            category="brand",
            decision_class="ops_change",
            status="approved",
            brands=["Brand A", "Brand B", "Brand C"],
            context_notes="Sustainability initiative - transition to recyclable materials by Q4",
            requester="brand_lead@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=25),
        ),
        Decision(
            id=new_id("dec"),
            statement="Launch green messaging campaign across home care portfolio",
            category="brand",
            decision_class="launch",
            status="approved",
            brands=["Brand D", "Brand E"],
            context_notes="Coordinate sustainability messaging to amplify impact",
            requester="marketing@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=18),
        ),
        Decision(
            id=new_id("dec"),
            statement="Update brand positioning to emphasize carbon neutrality",
            category="brand",
            decision_class="brand_positioning",
            status="approved",
            brands=["Brand F", "Brand G", "Brand H"],
            context_notes="Align all brands with sustainability theme",
            requester="brand_ops@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        ),
    ]
    
    # Pattern 4: Concentration risk (8 brands depending on single vendor)
    concentration_decisions = [
        Decision(
            id=new_id("dec"),
            statement="Continue partnership with Critical Vendor Z for specialty chemicals",
            category="procurement",
            decision_class="vendor_selection",
            status="approved",
            brands=["Brand A", "Brand B", "Brand C", "Brand D"],
            context_notes="Critical Vendor Z is sole supplier for key ingredient",
            requester="procurement@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
        ),
        Decision(
            id=new_id("dec"),
            statement="Expand contract with Critical Vendor Z for additional product lines",
            category="procurement",
            decision_class="contract",
            status="executed",
            brands=["Brand E", "Brand F", "Brand G", "Brand H"],
            context_notes="Adding 4 more brands to Vendor Z portfolio",
            requester="procurement_lead@think9.com",
            created_at=datetime.now(timezone.utc) - timedelta(days=7),
        ),
    ]
    
    # Add all decisions to database
    all_decisions = vendor_decisions + ingredient_decisions + sustainability_decisions + concentration_decisions
    for decision in all_decisions:
        db.add(decision)
    
    db.commit()
    print(f"✓ Seeded {len(all_decisions)} sample decisions")
    return [d.id for d in all_decisions]


def test_decision_pattern_scan():
    """Test the decision pattern scanning functionality."""
    db = SessionLocal()
    
    print("\n" + "="*70)
    print("TESTING DECISION AGGREGATION - MULTI-BRAND PATTERN DETECTION")
    print("="*70)
    
    # Seed sample data
    print("\n1. Seeding sample decisions...")
    decision_ids = seed_sample_decisions()
    
    # Run pattern scan
    print("\n2. Scanning decisions for multi-brand patterns...")
    service = DecisionAggregationService(db)
    report = service.scan_decisions(
        since_days=45,
        min_brands=2,
        min_score=0.5,
        report_type="ad_hoc",
    )
    
    # Display results
    print(f"\n3. SCAN RESULTS:")
    print(f"   - Brands scanned: {report.summary.total_brands_scanned}")
    print(f"   - Decisions analyzed: {report.summary.total_documents_scanned}")
    print(f"   - Clusters found: {report.summary.clusters_found}")
    print(f"   - Opportunities identified: {report.summary.opportunities_found}")
    print(f"   - Risks flagged: {report.summary.risks_found}")
    print(f"   - Execution triggers fired: {report.summary.triggers_fired}")
    print(f"   - Estimated value created: ${report.summary.estimated_value_created:,.2f}")
    
    # Display clusters
    print(f"\n4. DETECTED CLUSTERS:")
    for i, cluster in enumerate(report.clusters, 1):
        print(f"\n   Cluster {i}: {cluster.title}")
        print(f"   - Dimension: {cluster.dimension}")
        print(f"   - Key: {cluster.key}")
        print(f"   - Affected brands: {', '.join(cluster.affected_brands)}")
        print(f"   - Decision count: {cluster.document_count}")
        print(f"   - Evidence count: {cluster.evidence_count}")
        print(f"   - Score: {cluster.score:.3f}")
        print(f"   - Recommended action: {cluster.recommended_action}")
        print(f"   - Execution target: {cluster.execution_target}")
    
    # Display opportunities
    print(f"\n5. CONSOLIDATION OPPORTUNITIES:")
    for i, opp in enumerate(report.opportunities, 1):
        print(f"\n   Opportunity {i}: {opp.opportunity_type}")
        print(f"   - {opp.title}")
        print(f"   - Brands: {', '.join(opp.affected_brands)}")
        print(f"   - Action: {opp.recommended_action}")
        print(f"   - Target: {opp.execution_target}")
    
    # Display risks
    print(f"\n6. PORTFOLIO RISKS:")
    for i, risk in enumerate(report.risks, 1):
        print(f"\n   Risk {i}: {risk.risk_type}")
        print(f"   - {risk.title}")
        print(f"   - Blast radius: {risk.blast_radius} brands")
        print(f"   - Action: {risk.recommended_action}")
    
    # Display triggers
    print(f"\n7. EXECUTION TRIGGERS:")
    for i, trigger in enumerate(report.triggers, 1):
        print(f"\n   Trigger {i}: {trigger.action}")
        print(f"   - Priority: {trigger.priority}")
        print(f"   - Target: {trigger.target}")
        print(f"   - Reason: {trigger.reason}")
        print(f"   - Should execute: {trigger.should_execute}")
    
    # Test monthly report
    print(f"\n8. TESTING MONTHLY REPORT GENERATION...")
    monthly_report = service.generate_monthly_report(
        month=datetime.now(timezone.utc).month,
        year=datetime.now(timezone.utc).year,
    )
    
    print(f"   Monthly Report Summary:")
    print(f"   - Clusters: {monthly_report.summary.clusters_found}")
    print(f"   - Opportunities: {monthly_report.summary.opportunities_found}")
    print(f"   - Estimated monthly value: ${monthly_report.summary.estimated_value_created:,.2f}")
    
    # Cleanup
    print(f"\n9. Cleaning up test data...")
    for decision_id in decision_ids:
        decision = db.get(Decision, decision_id)
        if decision:
            db.delete(decision)
    db.commit()
    print(f"✓ Cleaned up {len(decision_ids)} test decisions")
    
    print("\n" + "="*70)
    print("TEST COMPLETED SUCCESSFULLY")
    print("="*70)
    
    db.close()


if __name__ == "__main__":
    test_decision_pattern_scan()
