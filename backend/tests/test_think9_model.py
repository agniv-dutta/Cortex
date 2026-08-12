from types import SimpleNamespace

from app.services.feedback.think9_model import _complexity_score, _output_quality, _similarity


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

