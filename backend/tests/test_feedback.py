"""Feedback-loop tests (docs/feedback-loops.md): outcome math, confidence
calibration fit/apply, and the precedent ranking boost."""

from app.services.feedback.analysis import accuracy_of, result_weight
from app.services.feedback.calibration import apply, fit
from app.services.feedback.precedent import boost_value
from app.services.feedback.reporting import _model_drift
from app.services.feedback.think9_model import Think9ModelService, _training_plan
from app.schemas.feedback import Think9TrainRequest

from datetime import datetime, timezone
from types import SimpleNamespace


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


def test_training_plan_marks_threshold_state():
    manifest = {
        "dataset_version": "think9-20260812-120000",
        "meets_min_samples": True,
        "training_objectives": [{"name": "supervised_finetune"}],
        "loss_functions": [{"name": "token_cross_entropy"}],
        "deployment_split": {"decision_brief": "fine-tuned Think9 model"},
    }
    request = SimpleNamespace(
        role="decision_brief",
        provider="anthropic",
        model_name="claude-sonnet-4",
        base_model="claude-sonnet-4-base",
        activate_on_success=True,
        min_samples=200,
        holdout_fraction=0.2,
    )

    plan = _training_plan(manifest, request)

    assert plan["status"] == "queued"
    assert plan["deployment_split"]["decision_brief"] == "fine-tuned Think9 model"
    assert plan["training_objectives"][0]["name"] == "supervised_finetune"


def test_model_drift_rollup_uses_eval_runs():
    eval_run = SimpleNamespace(
        kind="eval",
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        id="run_eval",
        status="completed",
        dataset_version="dv1",
        samples=10,
        payload={"mode": "historical"},
        metrics={
            "comparison": {
                "win_rate": 0.7,
                "match_delta": 0.12,
                "confidence_mae_delta": 0.04,
                "citation_overlap_delta": 0.08,
                "format_compliance_delta": 0.03,
            }
        },
    )
    train_run = SimpleNamespace(
        kind="train",
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        id="run_train",
        status="queued",
        dataset_version="dv0",
        samples=200,
        payload={"request": {"model_name": "claude-sonnet-4"}},
        metrics={"training_rows": 160, "holdout_rows": 40},
    )
    deploy_run = SimpleNamespace(
        kind="deploy",
        created_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        id="run_deploy",
        status="completed",
        dataset_version="dv0",
        samples=0,
        payload={"provider": "anthropic"},
        metrics={"active": True},
    )

    drift = _model_drift([train_run, deploy_run, eval_run])

    assert drift.runs_recorded == 3
    assert drift.win_rate and drift.win_rate[0].value == 0.7
    assert drift.latest_eval["id"] == "run_eval"
    assert drift.latest_train["id"] == "run_train"
    assert drift.latest_deploy["id"] == "run_deploy"


def test_train_enqueues_background_job(monkeypatch):
    captured = {}

    class FakeSession:
        def __init__(self) -> None:
            self.items = []
            self.commits = 0

        def add(self, item) -> None:
            self.items.append(item)

        def commit(self) -> None:
            self.commits += 1

    def fake_delay(run_id, payload):
        captured["run_id"] = run_id
        captured["payload"] = payload
        return SimpleNamespace(id="task-123")

    monkeypatch.setattr("app.workers.tasks.train_think9_model_task.delay", fake_delay)

    service = Think9ModelService(FakeSession())
    response = service.train(
        Think9TrainRequest(
            role="decision_brief",
            provider="anthropic",
            model_name="claude-sonnet-4",
            base_model="claude-sonnet-4-base",
            holdout_fraction=0.2,
            min_samples=200,
            activate_on_success=False,
            notes="test run",
        )
    )

    assert response.status == "queued"
    assert response.task_id == "task-123"
    assert captured["run_id"] == response.run_id
    assert captured["payload"]["model_name"] == "claude-sonnet-4"
    assert service.session.commits == 1
    assert service.session.items[0].kind == "train"
