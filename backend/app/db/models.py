"""
app/db/models.py

SQLAlchemy ORM models for the RAG knowledge assistant.

Tables:
  - documents   : one row per ingested file (from Drive or local disk)
  - chunks      : text chunks with 384-dim pgvector embeddings
  - query_logs  : every user query and its generated answer + metadata
  - sync_state  : last-seen sync timestamp per source (drive / local)

The pgvector `Vector` column type is imported from the pgvector package.
JSONB columns are used for metadata and arrays to avoid schema churn when
field shapes evolve.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# ── Document ──────────────────────────────────────────────────────────────────

class Document(Base):
    """
    Represents a single ingested source document.

    `file_id` is the stable identifier used to detect duplicates:
      - For Google Drive files: the Drive file ID.
      - For local files: a hash of the absolute path.
    `access_group` is an arbitrary string defined by the organisation
    (e.g. "engineering", "hr", "finance") — no values are hardcoded here.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="'drive' or 'local'"
    )
    access_group: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Arbitrary access-control group string; matched against JWT groups.",
    )
    drive_folder: Mapped[str | None] = mapped_column(String(512), nullable=True)
    modified_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationship – cascades deletes so orphaned chunks are removed with document
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} file_name={self.file_name!r}>"


# ── Chunk ─────────────────────────────────────────────────────────────────────

class Chunk(Base):
    """
    A text chunk derived from a Document, storing its vector embedding.

    `chunk_id` is a stable, unique string (e.g. "<file_id>-<chunk_index>")
    used to detect duplicates during re-indexing without relying on the
    auto-generated UUID primary key.

    `embedding` stores the 384-dimensional float32 vector produced by
    BAAI/bge-small-en-v1.5.  The HNSW index on this column is created by
    the 001_init_pgvector.sql migration.

    `metadata_` (note the trailing underscore to avoid shadowing Python's
    built-in) stores arbitrary per-chunk metadata as JSONB, e.g. section
    headings, table markers, or OCR confidence scores.
    """

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_chunks_chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chunk_id: Mapped[str] = mapped_column(
        String(512), unique=True, nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(
        Vector(384), nullable=False,
        comment="384-dim float32 vector from BAAI/bge-small-en-v1.5.",
    )
    access_group: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Copied from the parent Document for fast WHERE filtering.",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk chunk_id={self.chunk_id!r} page={self.page_number}>"


# ── QueryLog ──────────────────────────────────────────────────────────────────

class QueryLog(Base):
    """
    Audit log for every query processed by the RAG pipeline.

    Stores enough information for:
      - Monitoring (latency, confidence distribution)
      - Debugging (which chunks were retrieved, what the rewritten query was)
      - Analytics (per-user / per-group usage patterns)

    `user_groups` is stored as a JSONB array because a user can belong to
    multiple groups simultaneously.
    """

    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    user_groups: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False,
        comment="JSON array of group strings from the user JWT.",
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False,
        comment="chunk_id values of all retrieved chunks (pre-rerank).",
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<QueryLog id={self.id} user={self.user_id!r}>"


# ── SyncState ─────────────────────────────────────────────────────────────────

class SyncState(Base):
    """
    Tracks the last successful sync timestamp for each document source.

    The scheduler uses this to perform incremental syncs — only files
    modified after `last_sync_time` are re-ingested on each poll cycle.
    `source` is either 'drive' or 'local'.
    """

    __tablename__ = "sync_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False,
        comment="'drive' or 'local'.",
    )
    last_sync_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SyncState source={self.source!r} last={self.last_sync_time}>"
