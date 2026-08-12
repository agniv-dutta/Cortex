"""Decision endpoints — brief generation, fetch, outcome recording (MVP §8.2–8.4)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Decision, DecisionBrief, Flag, Outcome
from app.schemas.api import DecisionCreateRequest, DecisionListItem, DecisionResponse, OutcomeRequest
from app.services.orchestrator import DecisionOrchestrator
from app.services.transparency import build_transparency_from_record

router = APIRouter(tags=["decisions"])


def _status_label(status: str) -> str:
    if status in {"approved", "executed"}:
        return "Approved"
    if status in {"rejected", "archived", "superseded"}:
        return "Rejected"
    return "Pending"


def _impact_score(outcome: Outcome | None) -> str | None:
    if outcome is None:
        return None
    deltas = outcome.metric_deltas or {}
    savings = deltas.get("savings_usd")
    cost = deltas.get("cost_usd")
    if isinstance(savings, (int, float)) and savings:
        return f"+${abs(float(savings)):.0f} Savings"
    if isinstance(cost, (int, float)) and cost:
        return f"-${abs(float(cost)):.0f} Cost"
    return outcome.result.title()


@router.get("/decisions", response_model=list[DecisionListItem])
def list_decisions(db: Session = Depends(get_db)) -> list[DecisionListItem]:
    decisions = db.query(Decision).order_by(Decision.created_at.desc()).limit(50).all()
    rows: list[DecisionListItem] = []
    for decision in decisions:
        brief = db.query(DecisionBrief).filter_by(decision_id=decision.id).order_by(DecisionBrief.created_at.desc()).first()
        outcome = db.get(Outcome, decision.id)
        recommendation = ((brief.brief or {}).get("recommended_action") or {}).get("action") if brief else None
        rows.append(
            DecisionListItem(
                id=decision.id,
                title=decision.statement,
                status=_status_label(decision.status),
                confidence=round((brief.confidence if brief and brief.confidence is not None else 0.0) * 100.0, 0),
                owner=decision.requester or "Lens",
                date=decision.created_at.strftime("%b %d, %Y") if decision.created_at else "",
                category=decision.category,
                description=recommendation or decision.context_notes or decision.statement,
                impactScore=_impact_score(outcome),
            )
        )
    return rows


@router.post("/decisions", response_model=DecisionResponse, status_code=201)
def create_decision(body: DecisionCreateRequest, db: Session = Depends(get_db)) -> DecisionResponse:
    orchestrator = DecisionOrchestrator(db)
    return orchestrator.run_decision(
        statement=body.statement,
        category=body.category,
        decision_class=body.decision_class,
        brands=body.brands,
        context_notes=body.context_notes,
        requester=body.requester,
    )


@router.get("/decisions/{decision_id}", response_model=DecisionResponse)
def get_decision(decision_id: str, db: Session = Depends(get_db)) -> DecisionResponse:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    brief = db.query(DecisionBrief).filter_by(decision_id=decision_id).order_by(DecisionBrief.created_at.desc()).first()
    flags = db.query(Flag).filter_by(brief_id=brief.id).all() if brief else []
    transparency = build_transparency_from_record(db, brief, flags) if brief else None
    return DecisionResponse(
        decision_id=decision.id,
        status=decision.status,
        brief=brief.brief if brief else None,
        confidence=brief.confidence if brief else None,
        flags=[{"flag_type": f.flag_type, "severity": f.severity, "conflict_text": f.conflict_text} for f in flags],
        provenance=brief.brief.get("provenance_chunks", []) if brief else [],
        model_info=brief.model_info if brief else None,
        transparency=transparency,
    )


@router.put("/decisions/{decision_id}/outcome")
def record_outcome(decision_id: str, body: OutcomeRequest, db: Session = Depends(get_db)) -> dict:
    if db.get(Decision, decision_id) is None:
        raise HTTPException(status_code=404, detail="decision not found")
    from app.services.feedback import FeedbackRecorder

    FeedbackRecorder().record_outcome(
        db,
        decision_id,
        result=body.result,
        metric_deltas=body.metric_deltas,
        narrative=body.narrative,
        recorded_by=body.recorded_by,
    )
    return {"decision_id": decision_id, "outcome_recorded": True}
