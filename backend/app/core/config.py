"""Centralised, environment-driven configuration (Pydantic Settings v2)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JARVIS_", env_file=".env", extra="ignore"
    )

    app_name: str = "JARVIS"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis"
    redis_url: str = "redis://localhost:6379/0"

    # NVIDIA NIM — hosted (build.nvidia.com) or self-hosted gateway.
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_api_key: str = ""
    nim_extra_endpoints: str = ""  # comma-separated additional gateway URLs

    obsidian_vault_path: str = "/data/vault"

    # NeMo Retriever (semantic memory)
    nim_embed_model: str = "nvidia/nv-embedqa-e5-v5"
    nim_rerank_model: str = "nvidia/llama-3.2-nv-rerankqa-1b-v2"
    # Hosted reranking lives behind a retrieval URL; leave empty to disable reranking.
    nim_rerank_url: str = ""
    context_token_budget: int = 4000

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    cors_origins: str = "http://localhost:3000"

    @property
    def nim_endpoints(self) -> list[str]:
        extra = [e.strip() for e in self.nim_extra_endpoints.split(",") if e.strip()]
        return [self.nim_base_url, *extra]

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
