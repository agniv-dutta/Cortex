"""GET /v1/playbooks â€” derive evidence-based playbooks from decisions."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.playbook import DerivedPlaybookResponse
from app.services.playbooks import derive_playbooks

router = APIRouter(tags=["playbooks"])


@router.get("/playbooks", response_model=list[DerivedPlaybookResponse])
def list_playbooks(
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DerivedPlaybookResponse]:
    return derive_playbooks(db, category=category)

