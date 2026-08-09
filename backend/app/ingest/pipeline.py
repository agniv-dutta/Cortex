"""Ingestion pipeline (ingestion-system.md §3): validate → persist-raw →
parse → chunk → embed → index. Idempotent by content sha256 (dedupe rule 1).
"""

import logging

from sqlalchemy.orm import Session

from app.core.ulid import new_id
from app.db.models import Chunk, Document
from app.ingest.chunker import chunk_text
from app.ingest.parsers import ParsedDocument
from app.providers.embedder import Embedder, get_embedder

logger = logging.getLogger(__name__)


class IngestPipeline:
    def __init__(self, session: Session, embedder: Embedder | None = None) -> None:
        self.session = session
        self.embedder = embedder or get_embedder()

    def ingest(self, doc: ParsedDocument, force_reprocess: bool = False) -> Document | None:
        """Normalize → chunk → embed → index. Returns the Document row (or None if dup)."""
        sha = doc.sha256
        existing = self.session.query(Document).filter_by(sha256=sha).first()
        if existing and not force_reprocess:
            logger.info("duplicate skipped (sha256=%s)", sha[:12])
            return None

        if existing:
            # content unchanged; treat as no-op unless forced (dedupe rule 6)
            logger.info("content identical (sha256=%s); no-op", sha[:12])
            return existing

        document = Document(
            id=new_id("doc"),
            doc_type=doc.doc_type,
            source=doc.source,
            title=doc.title,
            version=doc.metadata.get("version", "1"),
            sha256=sha,
            status="active",
            category=doc.category,
            brands=doc.brands,
            metadata_=doc.metadata,
            raw_ref=f"s3://raw/{doc.source}/{sha}",
        )
        self.session.add(document)
        self.session.flush()

        specs = chunk_text(doc.content, doc.doc_type)
        contents = [s.content for s in specs]
        vectors = self.embedder.embed(contents)

        for index, (spec, vector) in enumerate(zip(specs, vectors)):
            chunk = Chunk(
                id=f"chunk_{sha}_{index}",
                document_id=document.id,
                chunk_index=index,
                content=spec.content,
                role=spec.role,
                section_path=spec.section_path or [],
                tokens=spec.tokens,
                embedding=vector,
            )
            self.session.add(chunk)

        logger.info("ingested doc_%s (%s, %d chunks)", document.id[:8], doc.doc_type, len(specs))
        return document
