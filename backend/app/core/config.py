"""
config.py — Application settings loaded from environment variables.

Uses pydantic-settings BaseSettings so every field can be overridden by an
environment variable of the same name (case-insensitive).  A .env file is
also supported for local development.
"""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the RAG backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ragdb"

    # ------------------------------------------------------------------
    # Embedding model
    # ------------------------------------------------------------------
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBED_DEVICE: str = "cpu"  # "cpu" | "cuda"

    # ------------------------------------------------------------------
    # LLM (Groq)
    # ------------------------------------------------------------------
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"

    # ------------------------------------------------------------------
    # Auth / JWT
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ------------------------------------------------------------------
    # Google Drive
    # ------------------------------------------------------------------
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    DRIVE_FOLDER_ID: str = ""
    DRIVE_ACCESS_GROUP: str = "default"
    DRIVE_POLL_INTERVAL_MINUTES: int = 15

    # ------------------------------------------------------------------
    # Reranker
    # ------------------------------------------------------------------
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # ------------------------------------------------------------------
    # MCP / API
    # ------------------------------------------------------------------
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"


settings = Settings()
