"""Feedback-loop tests (docs/feedback-loops.md): outcome math, confidence
calibration fit/apply, and the precedent ranking boost."""

from app.services.feedback.analysis import accuracy_of, result_weight
from app.services.feedback.calibration import apply, fit
from app.services.feedback.precedent import boost_value


def test_result_weight():
    assert result_weight("success") == 1.0
    assert result_weight("partial") == 0.5
    assert result_weight("failure") == 0.0
    assert result_weight("superseded") is None


def test_accuracy_of():
    assert accuracy_of([]) == 0.0


def test_calibration_fit_and_apply_are_monotone():
    pairs = [
        (0.9, "success"), (0.9, "success"), (0.9, "failure"),
        (0.7, "success"), (0.7, "failure"),
        (0.5, "success"), (0.5, "failure"), (0.5, "failure"), (0.5, "failure"), (0.5, "failure"),
        (0.4, "failure"), (0.4, "failure"),
        (0.3, "success"), (0.3, "success"), (0.3, "failure"),
        (0.25, "failure"), (0.25, "failure"), (0.25, "failure"),
    ]
    payload = fit(pairs)
    assert payload["samples"] == len(pairs)
    assert payload["points"], "expected at least one bucket"

    xs = [p["x"] for p in payload["points"]]
    ys = [p["y"] for p in payload["points"]]
    assert xs == sorted(xs)
    assert all(a <= b for a, b in zip(ys, ys[1:])), "curve must be non-decreasing"
    assert all(0.2 <= p["y"] <= 1.0 for p in payload["points"])

    out = [apply(payload, c) for c in (0.25, 0.5, 0.75, 1.0)]
    assert all(0.2 <= c <= 1.0 for c in out)


def test_calibration_apply_empty_payload_passthrough():
    assert apply({"points": [], "global_success": 0.0}, 0.8) == 0.8
    assert apply({}, 0.42) == 0.42
    assert apply({"points": []}, 0.05) == 0.2  # floored


def test_calibration_high_confidence_high_success_maps_high():
    pairs = [(0.95, "success") for _ in range(12)] + [(0.25, "failure") for _ in range(12)]
    payload = fit(pairs)
    assert apply(payload, 0.9) >= apply(payload, 0.3)


def test_boost_value_gating():
    assert boost_value(accuracy=0.9, used_count=2) == 0.0  # under-sampled
    assert boost_value(accuracy=0.5, used_count=5) == 0.0  # below min accuracy
    assert boost_value(accuracy=1.0, used_count=5) == 0.15  # max boost
    assert boost_value(accuracy=0.8, used_count=5) == 0.075  # half of max
    assert boost_value(accuracy=0.6, used_count=3) == 0.0  # exactly at the floor
    assert boost_value(accuracy=0.7, used_count=3) > 0.0  # just above


def test_boost_value_never_negative():
    assert boost_value(accuracy=0.0, used_count=0) >= 0.0
    assert boost_value(accuracy=0.99, used_count=99) >= 0.0
