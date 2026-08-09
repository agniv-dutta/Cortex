"""Expert-agent layer tests (docs/expert-agents.md)."""

from app.core.config import Settings
from app.core.envelope import StageName, WorkflowContext, WorkflowInput
from app.schemas.brief import DraftBrief, RecommendedAction
from app.schemas.context import QueryContext, RetrievedContext
from app.schemas.expert import EscalationFlag, ExpertAssessment, ExpertConstraint, ExpertRisk
from app.services.experts import (
    MetaAgent,
    detect_conflicts,
    hard_constraints_conflict,
    merge_risks,
    panel_for,
    resolve,
    run_expert_panel,
)
from app.services.experts.routing import CANONICAL_ORDER, CATEGORY_AGENTS


def _qc(category: str, **kw) -> QueryContext:
    return QueryContext(category=category, category_confidence=0.9, **kw)


def _assessment(agent: str, verdict: str, constraints=None, escalate=None) -> ExpertAssessment:
    return ExpertAssessment(
        agent=agent,
        verdict=verdict,
        summary=f"{agent} assessment",
        risks=[ExpertRisk(risk=f"{agent} risk", severity="medium")],
        constraints=constraints or [],
        escalate=escalate or EscalationFlag(),
        confidence=0.8,
    )


def _brief(confidence: float = 0.8) -> DraftBrief:
    return DraftBrief(recommended_action=RecommendedAction(action="accept the offer", confidence=confidence))


# ---------------------------------------------------------------------- routing
def test_panel_for_procurement():
    qc = _qc("procurement")
    assert panel_for(qc) == ["legal", "financial", "supply_chain", "operations"]


def test_panel_for_legal():
    assert panel_for(_qc("legal")) == ["legal", "financial"]


def test_panel_for_expertise_augments_map():
    qc = _qc("brand", required_expertise=["cfo", "supply_chain_manager"])
    panel = panel_for(qc)
    assert set(panel) == {"brand", "operations", "financial", "supply_chain"}
    assert panel == [a for a in CANONICAL_ORDER if a in set(panel)]


def test_all_categories_map_to_canonical_agents():
    for category, agents in CATEGORY_AGENTS.items():
        assert all(a in CANONICAL_ORDER for a in agents)


# ------------------------------------------------------------ conflict detection
def test_hard_constraint_conflict_detected():
    assert hard_constraints_conflict("Must accept MOQ of 50K units", "Do not accept MOQ above 25K units")


def test_hard_constraint_no_conflict():
    assert not hard_constraints_conflict("Must accept MOQ of 50K units", "Require net 60 payment terms")


def test_detect_verdict_split():
    panel = [_assessment("legal", "support"), _assessment("financial", "oppose")]
    conflicts = detect_conflicts(panel)
    assert any(c.type == "verdict" for c in conflicts)


def test_detect_no_conflict_when_unanimous():
    panel = [_assessment("legal", "support"), _assessment("financial", "support")]
    assert detect_conflicts(panel) == []


# ------------------------------------------------------------- meta synthesis
def test_resolve_unanimous_approve():
    panel = [_assessment("legal", "support"), _assessment("financial", "support")]
    meta, _ = resolve(_brief(), panel)
    assert meta.final_status == "approve"
    assert meta.final_confidence == 0.85  # 0.8 + unanimous bonus
    assert meta.agreement == 1.0
    assert meta.escalations == []


def test_resolve_minority_veto_is_conditional():
    panel = [
        _assessment("legal", "support"),
        _assessment("financial", "oppose"),
        _assessment("supply_chain", "support"),
    ]
    meta, _ = resolve(_brief(), panel)
    assert meta.final_status == "conditionally_approve"
    assert "financial" in meta.unified_brief["vetoes"]
    assert meta.final_confidence == 0.65  # 0.8 - 0.15 veto penalty


def test_resolve_majority_oppose_escalates():
    panel = [
        _assessment("legal", "oppose"),
        _assessment("financial", "oppose"),
        _assessment("supply_chain", "support"),
    ]
    meta, _ = resolve(_brief(), panel)
    assert meta.final_status == "escalate"
    assert any(e.to == "executive" for e in meta.escalations)


def test_resolve_hard_constraint_conflict_escalates():
    hard_a = ExpertConstraint(constraint="Must accept MOQ of 50K units", type="hard")
    hard_b = ExpertConstraint(constraint="Do not accept MOQ above 25K units", type="hard")
    panel = [
        _assessment("supply_chain", "support", constraints=[hard_a]),
        _assessment("financial", "support", constraints=[hard_b]),
    ]
    meta, _ = resolve(_brief(), panel)
    assert meta.final_status == "escalate"
    assert any("hard-constraint conflict" in u for u in meta.unresolved_conflicts)


def test_resolve_agent_escalation_flag_forwards():
    panel = [
        _assessment("legal", "support", escalate=EscalationFlag(flag=True, reason="ambiguous contract text", to="legal_counsel")),
        _assessment("financial", "support"),
    ]
    meta, _ = resolve(_brief(), panel)
    assert meta.final_status == "escalate"
    assert any(e.to == "legal_counsel" for e in meta.escalations)


def test_resolve_confidence_floor():
    panel = [_assessment("legal", "support"), _assessment("financial", "oppose")]
    meta, _ = resolve(_brief(confidence=0.1), panel)
    assert meta.final_confidence == 0.2
    assert meta.final_status == "escalate"


def test_merge_risks_keeps_max_severity():
    panel = [
        ExpertAssessment(agent="legal", risks=[ExpertRisk(risk="contract risk", severity="high")]),
        ExpertAssessment(agent="legal", risks=[ExpertRisk(risk="contract risk", severity="critical")]),
        ExpertAssessment(agent="financial", risks=[ExpertRisk(risk="budget risk", severity="low")]),
    ]
    merged = merge_risks(panel)
    assert merged["legal"]["severity"] == "critical"
    assert merged["financial"]["severity"] == "low"


# ------------------------------------------------------------ panel integration
class _FakeLLM:
    model = "fake-expert"

    def complete(self, system, user, *, temperature=0.0, max_tokens=800, json_mode=True):
        return (
            '{"agent":"x","verdict":"support","summary":"ok",'
            '"risks":[{"risk":"r1","severity":"low","evidence":"e"}],'
            '"opportunities":[],"constraints":[],"recommendation":"go",'
            '"confidence":0.9,"escalate":{"flag":false,"reason":"","to":""},"assumptions":[]}'
        )


def test_run_expert_panel_stamps_and_returns_assessments(monkeypatch):
    from app.services.experts import agents as agents_module

    monkeypatch.setattr(agents_module, "get_llm", lambda *a, **k: _FakeLLM())

    env = WorkflowContext(
        trace_id="t",
        input=WorkflowInput(question="accept the 50K MOQ?"),
        stage={"name": "orchestrator", "attempt": 1, "status": "ok"},
    )
    qc = _qc("procurement")
    rc = RetrievedContext()
    brief = _brief()

    settings = Settings(expert_agents_enabled=True)
    assessments = run_expert_panel(env, qc, rc, brief, settings=settings)

    assert [a.agent for a in assessments] == ["legal", "financial", "supply_chain", "operations"]
    assert all(a.status == "ok" for a in assessments)
    stamps = [s for s in env.provenance if s.agent == StageName.E1_EXPERT_PANEL.value]
    assert len(stamps) == 4


def test_meta_agent_refine_off_is_deterministic():
    panel = [_assessment("legal", "support"), _assessment("financial", "support")]
    env = WorkflowContext(
        trace_id="t",
        input=WorkflowInput(question="go?"),
        stage={"name": "orchestrator", "attempt": 1, "status": "ok"},
    )
    meta, stamp = MetaAgent().synthesize(env, _brief(), panel, "procurement", refine=False)
    assert meta.final_status == "approve"
    assert stamp.agent == StageName.E2_META.value
