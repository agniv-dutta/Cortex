"""Admin / ops endpoints (MVP §10.2, ingestion-system.md §4)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Chunk, Decision, Document, Flag, Query

router = APIRouter(tags=["admin"])


@router.get("/admin/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    return {
        "documents": db.query(func.count(Document.id)).scalar() or 0,
        "chunks": db.query(func.count(Chunk.id)).scalar() or 0,
        "decisions": db.query(func.count(Decision.id)).scalar() or 0,
        "queries": db.query(func.count(Query.id)).scalar() or 0,
        "flags": db.query(func.count(Flag.id)).scalar() or 0,
    }
