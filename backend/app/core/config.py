"""Application settings. All knobs referenced from docs/retrieval-system.md §3 and
docs/cost-performance-analysis.md."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "think9-backend"
    app_env: str = "dev"
    log_level: str = "INFO"
    api_v1_prefix: str = "/v1"

    # ---- infra ----
    database_url: str = "postgresql+psycopg2://think9:think9@localhost:5432/think9"
    redis_url: str = "redis://localhost:6379/0"

    # ---- embeddings ----
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 64

    # ---- LLM tiers ----
    cheap_model: str = "gpt-4o-mini"
    cheap_provider: str = "openai"
    premium_model: str = "claude-sonnet-4-20250514"
    premium_provider: str = "anthropic"

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # ---- hybrid ranking weights (retrieval-system.md §3.2) ----
    hybrid_w_semantic: float = 0.50
    hybrid_w_bm25: float = 0.25
    hybrid_w_category: float = 0.15
    hybrid_w_freshness: float = 0.10

    # ---- retrieval thresholds (retrieval-system.md §3.6) ----
    retrieve_ok_threshold: float = 0.55
    retrieve_weak_threshold: float = 0.35

    # ---- generation ----
    context_token_budget: int = 4000
    rerank_top_k: int = 40
    context_top_k: int = 12
    max_revision_rounds: int = 2
    cost_budget_usd: float = 1.00

    # ---- app ----
    cors_origins: list[str] = ["http://localhost:3000"]

    # ---- expert agents (expert-agents.md) ----
    expert_agents_enabled: bool = True
    expert_parallelism: int = 5
    expert_llm_tier: str = "premium"

    # ---- feedback loops (feedback-loops.md §3.2) ----
    precedent_boost_max: float = 0.15
    precedent_min_accuracy: float = 0.6
    precedent_min_uses: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
