"""Tests for the decision transparency payload builder."""

from types import SimpleNamespace

from app.schemas.brief import ConfidenceChecks, DraftBrief, MissingContextAlert, RecommendedAction, Validation
from app.services.transparency import build_transparency_from_record, build_transparency_from_retrieval


def _brief() -> DraftBrief:
    return DraftBrief(
        recommended_action=RecommendedAction(action="Negotiate MOQ", confidence=0.87),
        precedents=[],
        risk_factors={},
        evidence_gaps=["No recent supply chain risk data"],
        provenance_chunks=["chunk-1", "chunk-2", "chunk-3"],
    )


def _validation() -> Validation:
    return Validation(
        verdict="pass",
        contradiction_flags=[],
        missing_context_alerts=[MissingContextAlert(type="region_risk", detail="No region telemetry", severity="low")],
        confidence_checks=ConfidenceChecks(evidence_density=0.67, citation_validity=1.0, confidence_rating="adequate"),
        revision_instructions=[],
        escalation_reasons=[],
    )


def test_build_transparency_from_retrieval_uses_retrieved_context():
    rc = SimpleNamespace(
        historical_decisions=[
            SimpleNamespace(
                decision_id="dec-1",
                title="Supplier Y negotiation (Feb 2024)",
                relevance=0.92,
                hybrid_score=0.9,
                recency_bias=0.4,
                match_reason="Closest match on MOQ",
                outcome_summary="Saved 12%",
                date="Feb 2024",
                chunk_refs=["chunk-1"],
            )
        ],
        playbook_sections=[
            SimpleNamespace(
                document_id="doc-2",
                section="Vendor policy",
                chunk_id="chunk-2",
                relevance=0.88,
                applies_because="Complies with active vendor policy",
            )
        ],
        general_context=[
            SimpleNamespace(
                chunk_id="chunk-3",
                document_id="doc-3",
                title="Supporting note",
                content="Supporting evidence for the recommendation.",
                doc_type="vendor",
                relevance=0.66,
                citation="[doc-3, chunk-3, vendor]",
            )
        ],
        evidence_gaps=[SimpleNamespace(type="missing_data", description="No recent supply chain risk data")],
    )

    class FakeQuery:
        def __init__(self, row):
            self.row = row

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self.row

    class FakeSession:
        def query(self, model):
            if getattr(model, "__name__", "") == "PrecedentStat":
                return FakeQuery(SimpleNamespace(accuracy=0.91, used_count=11))
            raise AssertionError(f"unexpected query: {model}")

    transparency = build_transparency_from_retrieval(FakeSession(), rc, _brief(), _validation())

    assert transparency.retrievedDocuments[0].title == "Supplier Y negotiation (Feb 2024)"
    assert transparency.retrievedDocuments[0].note == "91% historical accuracy across 11 uses"
    assert transparency.confidenceReasoning[0].summary.startswith("Validator rated evidence")
    assert transparency.playbookChecks[0].passed is True
    assert transparency.missingData[0].label == "Region Risk"


def test_build_transparency_from_record_returns_stored_payload():
    stored = {
        "retrievedDocuments": [{"id": "doc-1", "title": "Stored doc", "source": "Playbook", "relevanceScore": 88, "explanation": "Stored explanation"}],
        "confidenceReasoning": [{"summary": "Stored confidence", "detail": "Stored detail"}],
        "playbookChecks": [{"check": "Stored check", "passed": True, "detail": "ok"}],
        "missingData": [{"label": "Stored gap", "detail": "missing"}],
    }
    brief_row = SimpleNamespace(brief={"transparency": stored}, confidence=0.76)

    transparency = build_transparency_from_record(SimpleNamespace(), brief_row, [])

    assert transparency.retrievedDocuments[0].title == "Stored doc"
    assert transparency.confidenceReasoning[0].summary == "Stored confidence"
