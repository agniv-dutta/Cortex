"""Chunk model — the atom of retrieval and citation (spec §4.1).

embedding column uses pgvector with dimensions matching the configured embedder
(app/core/config.py EMBEDDING_DIMENSIONS). The HNSW index is created in
scripts/init_db.py (not in migrations) to keep the migration portable.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.database import Base

settings = get_settings()


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="body")
    section_path: Mapped[list] = mapped_column(JSONB, default=list)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list] = mapped_column(Vector(settings.embedding_dimensions), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")  # noqa: F821
