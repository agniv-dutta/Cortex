"""Embedder interface + implementations (spec §5, ingestion spec §3.3).

Swap-in by config: OpenAIEmbedder is the MVP default; FakeEmbedder provides
deterministic embeddings for tests and offline seeding (no API key required).
A BGE-M3 self-hosted profile can be added later behind the same interface.
"""

import hashlib
from abc import ABC, abstractmethod

from app.core.config import get_settings


class Embedder(ABC):
    model_version: str
    dimensions: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one normalized vector per text."""


class OpenAIEmbedder(Embedder):
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        batch_size: int = 64,
        api_key: str | None = None,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.model_version = f"{model}@1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAIError

        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            try:
                resp = self._client.embeddings.create(model=self.model, input=batch)
            except OpenAIError as exc:  # pragma: no cover
                raise RuntimeError(f"embedding failure: {exc}") from exc
            ordered = sorted(resp.data, key=lambda d: d.index)
            out.extend([d.embedding for d in ordered])
        return out


class FakeEmbedder(Embedder):
    """Deterministic content-hash embeddings — functional, not semantic.

    Used for smoke tests and `--fake-embeddings` seeding so the pipeline runs
    without API keys. Quality is meaningless; do not rely on retrieval metrics.
    """

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions
        self.model_version = "fake@1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vec = [((digest[i % len(digest)] or 1) / 255.0) - 0.5 for i in range(self.dimensions)]
            norm = (sum(x * x for x in vec)) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out


def get_embedder() -> Embedder:
    settings = get_settings()
    if not settings.openai_api_key:
        return FakeEmbedder(dimensions=settings.embedding_dimensions)
    return OpenAIEmbedder(
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
        api_key=settings.openai_api_key,
    )
