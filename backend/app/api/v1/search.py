"""GET /v1/search — corpus search for the dashboard (MVP §8.6)."""

from fastapi import APIRouter, Depends
from fastapi import Query as QueryParam
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.providers.embedder import get_embedder
from app.providers.vectorstore import PgVectorStore
from app.schemas.api import SearchResponse, SearchResult

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    q: str,
    category: str | None = QueryParam(None),
    brand: str | None = QueryParam(None),
    doc_type: str | None = QueryParam(None),
    limit: int = QueryParam(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> SearchResponse:
    embedder = get_embedder()
    store = PgVectorStore(db)
    embedding = embedder.embed([q])[0]
    hits = store.hybrid_search(
        embedding,
        q,
        category=category,
        brands=[brand] if brand else None,
        doc_types=[doc_type] if doc_type else None,
        top_k=limit,
    )
    results = [
        SearchResult(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            title=h.title,
            snippet=h.content[:300],
            score=round(h.hybrid_score, 3),
            source=h.doc_type,
            date=str(h.created_at.date()) if h.created_at else None,
        )
        for h in hits
    ]
    return SearchResponse(results=results, total=len(results))
