"""pgvector-backed hybrid retrieval (retrieval-system.md §3, §6).

Two-stage approach implemented here:
1. Candidate generation: dense (HNSW cosine) and sparse (Postgres FTS) queries
   run in parallel against active documents with optional ACL/category/brand filters.
2. Score fusion in Python: min-max normalization, then
   hybrid = w_sem·semantic + w_bm·bm25 + w_cat·category_boost + w_age·freshness
   (defaults 0.50 / 0.25 / 0.15 / 0.10 per retrieval-system.md §3.2).

A cross-encoder re-ranker is intentionally not part of the MVP (retrieval doc §3.5).
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Chunk, Document

# retrieval-system.md §3.3 — category → doc_type boost
CATEGORY_BOOSTS: dict[str, dict[str, float]] = {
    "procurement": {"vendor": 0.20, "negotiation": 0.20, "contract": 0.20, "playbook": 0.20, "meeting": 0.0},
    "brand": {"playbook": 0.15, "postmortem": 0.15, "meeting": 0.15, "feedback_summary": 0.15},
    "product": {"launch": 0.15, "postmortem": 0.15, "meeting": 0.15, "feedback_summary": 0.15},
    "hr": {"meeting": 0.15, "guideline": 0.15},
    "legal": {"contract": 0.20, "template": 0.20, "decision": 0.20},
    "ops": {"meeting": 0.10, "decision": 0.10, "guideline": 0.10},
}

# retrieval-system.md §3.4 — freshness half-life (days) by doc_type
HALF_LIFE_DAYS: dict[str, int] = {
    "playbook": 30,
    "guideline": 30,
    "meeting": 180,
    "meeting_summary": 180,
    "decision": 365,
    "postmortem": 365,
    "learning": 365,
    "contract": 730,
    "vendor": 730,
    "negotiation": 365,
    "launch": 365,
    "feedback_summary": 365,
    "email": 90,
    "action_item": 90,
    "slack_digest": 180,
}

DEFAULT_HALF_LIFE = 365


@dataclass
class ScoredChunk:
    chunk_id: str
    document_id: str
    title: str
    content: str
    doc_type: str
    category: str | None
    status: str
    created_at: datetime | None
    semantic_score: float = 0.0
    bm25_score: float = 0.0
    category_score: float = 0.0
    freshness_score: float = 0.0
    hybrid_score: float = 0.0


class PgVectorStore:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    # candidate generation
    # ------------------------------------------------------------------ #
    def _base_filters(self, category: str | None, brands: list[str] | None, doc_types: list[str] | None):
        filters = [Document.status == "active"]
        if category:
            filters.append(Document.category == category)
        if brands and "all" not in brands:
            filters.append(Document.brands.op("?|")(brands))
        if doc_types:
            filters.append(Document.doc_type.in_(doc_types))
        return and_(*filters)

    def _dense_search(
        self,
        query_embedding: list[float],
        category: str | None,
        brands: list[str] | None,
        doc_types: list[str] | None,
        limit: int = 40,
    ) -> list[ScoredChunk]:

        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Document.title,
                Chunk.content,
                Document.doc_type,
                Document.category,
                Document.status,
                Chunk.created_at,
                (1.0 - Chunk.embedding.cosine_distance(query_embedding)).label("sim"),
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(self._base_filters(category, brands, doc_types))
            .order_by(text("sim DESC"))
            .limit(limit)
        )
        return [self._row_to_chunk(row, "sim") for row in self.session.execute(stmt)]

    def _bm25_search(
        self,
        query_text: str,
        category: str | None,
        brands: list[str] | None,
        doc_types: list[str] | None,
        limit: int = 20,
    ) -> list[ScoredChunk]:
        ts_query = func.plainto_tsquery("english", query_text)
        ts_rank = func.ts_rank(func.to_tsvector("english", Chunk.content), ts_query).label("rank")
        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Document.title,
                Chunk.content,
                Document.doc_type,
                Document.category,
                Document.status,
                Chunk.created_at,
                ts_rank,
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(self._base_filters(category, brands, doc_types))
            .where(func.to_tsvector("english", Chunk.content).op("@@")(ts_query))
            .order_by(text("rank DESC"))
            .limit(limit)
        )
        return [self._row_to_chunk(row, "rank") for row in self.session.execute(stmt)]

    @staticmethod
    def _row_to_chunk(row, score_col: str) -> ScoredChunk:
        return ScoredChunk(
            chunk_id=row.id,
            document_id=row.document_id,
            title=row.title,
            content=row.content,
            doc_type=row.doc_type,
            category=row.category,
            status=row.status,
            created_at=row.created_at,
            semantic_score=float(getattr(row, score_col, 0.0) or 0.0),
        )

    # ------------------------------------------------------------------ #
    # scoring helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _minmax(values: dict[str, float]) -> dict[str, float]:
        if not values:
            return {}
        low, high = min(values.values()), max(values.values())
        if high == low:
            return {k: 1.0 for k in values}
        return {k: (v - low) / (high - low) for k, v in values.items()}

    def _category_score(self, category: str | None, doc_type: str) -> float:
        if not category:
            return 0.0
        return CATEGORY_BOOSTS.get(category, {}).get(doc_type, 0.0)

    def _freshness_score(self, doc_type: str, created_at: datetime | None) -> float:
        if created_at is None:
            return 0.0
        days = max(0.0, (datetime.now() - created_at).total_seconds() / 86400)
        half_life = HALF_LIFE_DAYS.get(doc_type, DEFAULT_HALF_LIFE)
        return float(pow(2, -days / half_life))

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        *,
        category: str | None = None,
        brands: list[str] | None = None,
        doc_types: list[str] | None = None,
        top_k: int = 40,
        dense_limit: int = 40,
        bm25_limit: int = 20,
    ) -> list[ScoredChunk]:
        dense = self._dense_search(query_embedding, category, brands, doc_types, limit=dense_limit)
        bm25 = self._bm25_search(query_text, category, brands, doc_types, limit=bm25_limit)

        merged: dict[str, ScoredChunk] = {}
        for chunk in dense:
            merged[chunk.chunk_id] = chunk
        for chunk in bm25:
            existing = merged.get(chunk.chunk_id)
            if existing:
                existing.bm25_score = chunk.semantic_score
            else:
                chunk.semantic_score = 0.0
                chunk.bm25_score = chunk.semantic_score
                merged[chunk.chunk_id] = chunk

        if not merged:
            return []

        sem_norm = self._minmax({cid: c.semantic_score for cid, c in merged.items()})
        bm_norm = self._minmax({cid: c.bm25_score for cid, c in merged.items()})

        w = self.settings
        results: list[ScoredChunk] = []
        for cid, chunk in merged.items():
            chunk.semantic_score = sem_norm.get(cid, 0.0)
            chunk.bm25_score = bm_norm.get(cid, 0.0)
            chunk.category_score = self._category_score(category, chunk.doc_type)
            chunk.freshness_score = self._freshness_score(chunk.doc_type, chunk.created_at)
            chunk.hybrid_score = (
                w.hybrid_w_semantic * chunk.semantic_score
                + w.hybrid_w_bm25 * chunk.bm25_score
                + w.hybrid_w_category * chunk.category_score
                + w.hybrid_w_freshness * chunk.freshness_score
            )
            results.append(chunk)

        results.sort(key=lambda c: c.hybrid_score, reverse=True)
        return results[:top_k]
