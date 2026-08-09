"""POST /v1/queries — ask a question (MVP API contract §8.1)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.api import QueryRequest, QueryResponse
from app.services.orchestrator import DecisionOrchestrator

router = APIRouter(tags=["queries"])


@router.post("/queries", response_model=QueryResponse)
def ask_question(body: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    orchestrator = DecisionOrchestrator(db)
    return orchestrator.run_query(
        question=body.question,
        channel=body.channel,
        user_id=body.user_id,
        session_id=body.session_id,
        context_notes=body.context_notes,
    )
