"""
app/config.py

Central configuration module for the RAG backend.
Uses Pydantic Settings to read all configuration from environment variables
(or a .env file during local development). A single `settings` singleton is
imported throughout the application so there is only one source of truth.

No group names are hardcoded here — access groups are purely runtime data
carried in JWT tokens and stored in the database.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration, sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://rag:rag_secret@localhost:5432/rag_db",
        description="Async SQLAlchemy connection string (asyncpg driver).",
    )

    # ── Embedding Model ───────────────────────────────────────────────────────
    embed_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="HuggingFace model ID for sentence embeddings (384-dim).",
    )
    embed_device: str = Field(
        default="cpu",
        description="Torch device for embedding inference. 'cpu' or 'cuda'.",
    )

    # ── Reranker Model ────────────────────────────────────────────────────────
    reranker_model: str = Field(
        default="BAAI/bge-reranker-base",
        description="HuggingFace cross-encoder model ID for reranking.",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: str = Field(default="groq")
    groq_api_key: str = Field(default="", description="Groq API key.")
    groq_model: str = Field(
        default="llama-3.1-70b-versatile",
        description="Groq model name for generation.",
    )

    # ── Auth / JWT ────────────────────────────────────────────────────────────
    jwt_secret: str = Field(
        default="change_me_in_production",
        description="HMAC secret used to sign JWTs. Must be long and random in prod.",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60)

    # ── Google Drive ──────────────────────────────────────────────────────────
    google_service_account_json: str = Field(
        default="/app/secrets/service_account.json",
        description="Path to the Google service-account credentials JSON file.",
    )
    drive_folder_id: str = Field(
        default="",
        description="Root Google Drive folder ID to sync. Empty string disables Drive sync.",
    )
    drive_poll_interval_minutes: int = Field(
        default=15,
        description="How often (minutes) the scheduler polls Google Drive.",
    )

    # ── Local Docs ────────────────────────────────────────────────────────────
    local_docs_path: str = Field(
        default="/app/local_docs",
        description="Container path where local documents are mounted.",
    )

    # ── MCP Server ────────────────────────────────────────────────────────────
    mcp_host: str = Field(default="0.0.0.0")
    mcp_port: int = Field(default=8001)

    # ── Retrieval Tuning ──────────────────────────────────────────────────────
    top_k_retrieval: int = Field(
        default=20,
        description="Number of chunks fetched from the vector store before reranking.",
    )
    top_k_reranked: int = Field(
        default=5,
        description="Number of chunks passed to the LLM after reranking.",
    )
    confidence_threshold: float = Field(
        default=0.4,
        description="Minimum reranker score to flag an answer as high-confidence.",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated allowed CORS origins.",
    )

    # ── Computed Properties ───────────────────────────────────────────────────

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_gpu_available(self) -> bool:
        """True when EMBED_DEVICE is set to 'cuda', allowing GPU inference."""
        return self.embed_device.lower() == "cuda"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins_list(self) -> List[str]:
        """Parsed list of CORS origins from the comma-separated env var."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def drive_sync_enabled(self) -> bool:
        """True when a Drive folder ID has been configured."""
        return bool(self.drive_folder_id)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton. Import this in other modules."""
    return Settings()


# Module-level singleton for convenient direct import:
#   from app.config import settings
settings: Settings = get_settings()
