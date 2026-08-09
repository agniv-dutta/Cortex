from app.schemas.context import CATEGORIES
from app.services.router import _rule_fallback


def test_rule_fallback_procurement():
    qc = _rule_fallback("Should we accept the 50K MOQ from the new ingredient vendor?")
    assert qc.category in CATEGORIES
    assert qc.category == "procurement"
    assert 0.0 < qc.category_confidence <= 0.7


def test_rule_fallback_legal():
    qc = _rule_fallback("Do we need indemnity protection for this exclusivity clause?")
    assert qc.category == "legal"


def test_rule_fallback_always_returns_valid():
    qc = _rule_fallback("zzz qqqx random")  # no known keywords
    assert qc.category in CATEGORIES
