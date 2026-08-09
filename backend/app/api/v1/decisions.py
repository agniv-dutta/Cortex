"""Decision endpoints — brief generation, fetch, outcome recording (MVP §8.2–8.4)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Decision, DecisionBrief, Flag
from app.schemas.api import DecisionCreateRequest, DecisionResponse, OutcomeRequest
from app.services.orchestrator import DecisionOrchestrator

router = APIRouter(tags=["decisions"])


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
    return DecisionResponse(
        decision_id=decision.id,
        status=decision.status,
        brief=brief.brief if brief else None,
        confidence=brief.confidence if brief else None,
        flags=[{"flag_type": f.flag_type, "severity": f.severity, "conflict_text": f.conflict_text} for f in flags],
        provenance=brief.brief.get("provenance_chunks", []) if brief else [],
        model_info=brief.model_info if brief else None,
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
