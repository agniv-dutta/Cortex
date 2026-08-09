"""Seed the 90-doc sample corpus (roadmap-mvp.md Week 1):
50 meeting transcripts, 10 brand playbooks, 30 historical decisions.

Usage:
    python scripts/seed_sample_data.py                 # uses configured embedder (needs key)
    python scripts/seed_sample_data.py --fake-embeddings  # deterministic fake vectors, no key

Includes deliberate contradictions (playbook MOQ rule vs a 2024 decision) so the
Week 3 contradiction scanner has something to find.
"""

import argparse
import logging

from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.ingest.parsers import mock_decision, mock_meeting, mock_playbook
from app.ingest.pipeline import IngestPipeline
from app.providers.embedder import FakeEmbedder, get_embedder

logger = logging.getLogger(__name__)

BRANDS = ["cortex", "protein", "wellness", "vita"]

PLAYBOOKS = [
    ("Cortex Brand Playbook", "Voice and tone: energetic, evidence-led.\nRule: Never accept an MOQ greater than 2x initial forecast without CFO approval.\nRule: Maintain at least two approved ingredient suppliers per SKU.\nRule: Renegotiate contracts at least 90 days before expiry.", "cortex"),
    ("Protein Brand Playbook", "Positioning: performance nutrition for athletes.\nRule: New ingredient vendors require a 3-month qualification batch.\nRule: Single-source ingredient supply requires documented justification and supply_chain_manager sign-off.", "protein"),
    ("Wellness Playbook", "Positioning: science-backed daily wellness.\nRule: Claims must be substantiated by published evidence.\nRule: Launch date freezes 6 weeks ahead; no exceptions without brand_lead sign-off.", "wellness"),
    ("Vita Playbook", "Positioning: plant-based complete nutrition.\nRule: MOQ commitments above forecast trigger cfo review.\nRule: Packaging changes require 8-week lead-time notice.", "vita"),
    ("Procurement Guidelines", "Rule: Net-30 standard; longer terms allowed for contracts over $1M.\nRule: Always benchmark 2+ quotes before vendor onboarding.\nRule: Escalate price increases above 5% to cfo.", "all"),
    ("Legal Guidelines", "Rule: Exclusivity clauses require ceo + legal_counsel sign-off.\nRule: Indemnity caps at 1x annual contract value by default.\nRule: NDAs must be reaffirmed at each renewal.", "all"),
    ("Launch Playbook", "Rule: Every launch gets a post-mortem within 30 days.\nRule: Capacity readiness review 8 weeks pre-launch.\nRule: Cross-functional go/no-go at 4 weeks pre-launch.", "all"),
    ("Supply Chain Playbook", "Rule: Maintain buffer stock for top-10 SKUs.\nRule: Vendor scorecards reviewed quarterly.\nRule: Any supply disruption > 48h requires an ops alert.", "all"),
    ("Pricing Playbook", "Rule: Price changes above 8% require cfo approval.\nRule: Promotional pricing needs brand_lead sign-off.\nRule: Volume discounts require a committed-volume contract.", "all"),
    ("Customer Experience Playbook", "Rule: NPS surveys on all launches.\nRule: Feedback summaries reviewed by product team monthly.\nRule: Escalate recurring complaints to product_head.", "all"),
]

DECISIONS = [
    ("Accept Supplier A MOQ of 50K for protein base", "Supplier offered a volume discount; warehouse capacity available.", "procurement", "partial"),
    ("Renegotiate corn protein contract before Q4", "Started early, gained +6% discount and extended lock-in.", "procurement", "success"),
    ("Walk away from Northwind pricing dispute", "Walk-away produced a better counteroffer within 3 weeks.", "procurement", "success"),
    ("Accept single-source whey supplier for 12 months", "Cost saving at risk; triggered resilience review.", "procurement", "failure"),
    ("Phased MOQ ramp with collagen vendor", "Split PO into tranches; volume pricing locked to cumulative volume.", "procurement", "success"),
    ("Drop Vendor X after SLA breaches", "Performance failed 3 consecutive quarterly scorecards.", "procurement", "success"),
    ("Approve 8% price increase on protein bars", "Passed cfo review; margin restored without share loss.", "pricing", "success"),
    ("Launch plant-based ready-to-drink in Q3", "Post-mortem: capacity gap at week 6; NPS 52.", "product", "partial"),
    ("Rebrand Wellness line messaging", "NPS +8 after 90 days.", "brand", "success"),
    ("Extend oats supplier contract 2 years", "Locks price, reduces flexibility; supply stable.", "procurement", "success"),
    ("Approve 2026 sponsorship spend", "Brand recall target met; cfo approved.", "brand", "success"),
    ("Retire legacy SKU line", "Free capacity; exit handled cleanly.", "product", "success"),
    ("Move fulfillment to regional 3PL", "SLA breach in month 2; ops alert raised.", "ops", "failure"),
    ("Increase MOQ to 2x forecast for packaging", "Playbook rule requires cfo approval; approved with mitigation.", "procurement", "partial"),
    ("Exclusivity for vitamin premix supplier", "CEO + legal sign-off obtained; terms capped.", "procurement", "partial"),
    ("Adopt 90-day payment terms for co-packer", "Allowed under >$1M contract; cash flow improved.", "procurement", "success"),
    ("Hire second supply chain analyst", "Reduced quote turnaround 3 days → 1.", "hr", "success"),
    ("Reorg brand team into pods", "Mixed retention; reverted after 6 months.", "hr", "failure"),
    ("Qualify second protein base supplier", "Resilience improved; qualification batch passed.", "procurement", "success"),
    ("Negotiate co-pack pricing with new supplier", "Benchmarked 2 quotes; landed 11% below incumbent.", "procurement", "success"),
    ("Change protein formula to reduce cost 12%", "Customer complaint uptick; formula reverted.", "product", "failure"),
    ("Launch subscription model pilot", "ACV +18% on pilot cohort.", "product", "success"),
    ("Extend warehouse lease 3 years", "Rates locked; capacity covers 2-year plan.", "ops", "success"),
    ("Accept 12% price increase on oats mid-contract", "Pushed back first; settled at 8% with volume commitment.", "procurement", "success"),
    ("Terminate co-pack agreement for repackaging", "Transitioned with 60-day ramp; no stockout.", "procurement", "success"),
    ("Approve new packaging artwork for protein", "8-week lead-time respected; launch on time.", "brand", "success"),
    ("Run brand recall campaign in Q1", "Recall +11%; cost per acquisition below target.", "brand", "success"),
    ("Build safety stock for top-10 SKUs", "No stockouts through peak; buffer policy adopted.", "ops", "success"),
    ("Switch ingredient testing lab", "Lead times improved; audit passed.", "procurement", "success"),
    ("Introduce vendor scorecards quarterly", "Three vendors exited program in year one.", "procurement", "success"),
]

MEETING_TOPICS = [
    "Q3 vendor strategy", "MOQ negotiation prep", "Brand voice review", "Launch go/no-go",
    "Supplier pricing dispute", "Capacity planning", "Customer feedback review", "Contract renewal",
    "Formulation change review", "Fulfillment ops", "Sponsorship decisions", "NPS deep dive",
]


def _build_meetings() -> list:
    meetings = []
    for i in range(50):
        topic = MEETING_TOPICS[i % len(MEETING_TOPICS)]
        brand = BRANDS[i % len(BRANDS)]
        body = (
            f"Meeting: {topic} ({i % 12 + 1}/2026)\n"
            f"Attendees: supply_chain, finance, brand\n"
            f"Topic: {topic}\n"
            f"Discussion: reviewed latest forecast and supplier options for {brand}.\n"
            f"Decision: {DECISIONS[i % len(DECISIONS)][0]} was discussed; owners assigned.\n"
            f"Owner: supply_chain_manager  Deadline: {(i % 4) + 2} weeks\n"
        )
        meetings.append(mock_meeting(title=f"{topic} #{i}", transcript=body, brands=[brand], meeting_id=f"mtg_{i}"))
    return meetings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake-embeddings", action="store_true", help="use deterministic fake vectors (no API key)")
    args = parser.parse_args()

    configure_logging("INFO")
    db = SessionLocal()
    try:
        embedder = FakeEmbedder() if args.fake_embeddings else get_embedder()
        logger.info("embedder: %s", embedder.model_version)
        pipeline = IngestPipeline(db, embedder)

        count = 0
        for title, content, brand in PLAYBOOKS:
            doc = mock_playbook(title, content, brands=[brand] if brand != "all" else BRANDS)
            if pipeline.ingest(doc):
                count += 1
        for statement, rationale, category, outcome in DECISIONS:
            if pipeline.ingest(mock_decision(statement, rationale, category, outcome)):
                count += 1
        for meeting in _build_meetings():
            if pipeline.ingest(meeting):
                count += 1

        db.commit()
        logger.info("seeded %d documents (50 meetings / 10 playbooks / 30 decisions)", count)
    finally:
        db.close()


if __name__ == "__main__":
    main()
