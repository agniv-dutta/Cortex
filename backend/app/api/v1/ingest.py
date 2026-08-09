"""Ingest endpoints (MVP §8.5, ingestion-system.md §4). MVP accepts manual
document payloads; provider webhook receivers are Phase 2 adapters."""


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.ulid import new_id
from app.ingest.parsers import ParsedDocument
from app.ingest.pipeline import IngestPipeline
from app.schemas.api import IngestRequest, IngestResponse

router = APIRouter(tags=["ingest"])


@router.post("/ingest/{source}", response_model=IngestResponse)
def trigger_ingest(source: str, body: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    """MVP ingest is a direct document write. source_ref accepts:
    {"title": str, "content": str, "doc_type": str, "category": str|None,
     "brands": [str], "metadata": {}}
    """
    if body.source != source:
        raise HTTPException(status_code=400, detail="path and body source mismatch")
    payload = body.source_ref
    content = payload.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="source_ref.content is required")

    parsed = ParsedDocument(
        doc_type=payload.get("doc_type", "guideline"),
        title=payload.get("title", "Untitled"),
        content=content,
        source=source,
        category=payload.get("category"),
        brands=payload.get("brands") or ["all"],
        metadata=payload.get("metadata") or {},
    )
    pipeline = IngestPipeline(db)
    document = pipeline.ingest(parsed, force_reprocess=body.force_reprocess)
    job_id = new_id("ing")
    if document is None:
        return IngestResponse(job_id=job_id, status="skipped_duplicate")
    return IngestResponse(job_id=job_id, status="completed", stages=["validate", "parse", "chunk", "embed", "index"])
