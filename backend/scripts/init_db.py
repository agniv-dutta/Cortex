"""Dev bootstrap: create tables + HNSW index (roadmap-mvp.md Week 1).

For a quick start, `create_all` is used instead of generated migrations. Use
`alembic revision --autogenerate -m "initial"` for production-grade migrations.
"""

import logging

from sqlalchemy import text

from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.db import models as _models  # noqa: F401

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging("INFO")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(
            text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks
                USING hnsw (embedding vector_cosine_ops) WITH (m = 32, ef_construction = 200)
            """)
        )
        conn.execute(
            text("""
                CREATE INDEX IF NOT EXISTS idx_chunks_fts ON chunks
                USING gin (to_tsvector('english', content))
            """)
        )
    logger.info("tables + indexes ready")


if __name__ == "__main__":
    main()
