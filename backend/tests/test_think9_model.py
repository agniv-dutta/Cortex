from types import SimpleNamespace

from app.services.feedback.think9_model import (
    _brief_format_score,
    _complexity_score,
    _loss_functions,
    _output_quality,
    _similarity,
    _training_objectives,
    _vendor_refs,
)


def test_output_quality_mapping():
    assert _output_quality("success") == "success"
    assert _output_quality("partial") == "partial"
    assert _output_quality("failure") == "failure"
    assert _output_quality("superseded") == "superseded"


def test_similarity_is_bounded():
    assert _similarity("Bundle MOQ for pasta", "Bundle MOQ for pasta") == 1.0
    assert 0.0 <= _similarity("A", "B") <= 1.0


def test_complexity_scores_clamp_to_five():
    decision = SimpleNamespace(category="procurement", decision_class="contract")
    brief = SimpleNamespace(brief={"precedents": [1, 2, 3, 4, 5]}, revision_round=2)
    flags = [SimpleNamespace(flag_type="contradicts"), SimpleNamespace(flag_type="risk")]
    assert _complexity_score(decision, brief, flags) == 5


def test_specialized_training_contract_is_explicit():
    objectives = _training_objectives()
    losses = _loss_functions()

    assert any(item["name"] == "domain_adaptation" for item in objectives)
    assert any(item["name"] == "citation_grounding_penalty" for item in losses)


def test_vendor_refs_and_brief_format_scoring():
    refs = _vendor_refs([
        "Negotiated with Supplier A on price and supply terms.",
        "Vendor X is likely to delay volume ramp.",
    ])

    assert "Supplier A" in refs
    assert "Vendor X" in refs
    assert _brief_format_score({"recommended_action": {}, "precedents": [], "risk_factors": {}, "approval_flow": {}, "evidence_gaps": [], "provenance_chunks": []}) < 1.0
