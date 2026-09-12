"""
schemas.py — Pydantic v2 models for vector store operations.

Defines the three core data-transfer objects used throughout the ML pipeline:

* SearchResult  — a single retrieved chunk returned from pgvector similarity search.
* ChunkUpsert   — the payload used when inserting/updating chunks in the DB.
* SearchQuery   — the input to the vector similarity search method.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel, Field, field_validator


class SearchResult(BaseModel):
    """A single chunk retrieved from the vector store."""

    chunk_id: str = Field(..., description="UUID of the chunk row.")
    document_id: str = Field(..., description="UUID of the parent document.")
    file_name: str = Field(..., description="Original file name.")
    page_number: int = Field(..., ge=0, description="0-indexed page/slide number.")
    text: str = Field(..., description="Raw chunk text.")
    score: float = Field(..., description="Cosine similarity score in [0, 1].")
    access_group: str = Field(..., description="Access-group string this chunk belongs to.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary per-chunk metadata.")

    model_config = {"frozen": True}


class ChunkUpsert(BaseModel):
    """Payload for inserting or updating a chunk in the vector store."""

    chunk_id: str = Field(..., description="Deterministic UUID for the chunk (PK).")
    document_id: str = Field(..., description="UUID of the parent document record.")
    file_name: str = Field(..., description="Original file name.")
    page_number: int = Field(..., ge=0)
    text: str = Field(..., description="Chunk text.")
    embedding: List[float] = Field(..., description="L2-normalised embedding vector (384-dim).")
    access_group: str = Field(..., description="Access-group string.")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("embedding")
    @classmethod
    def validate_embedding_length(cls, v: List[float]) -> List[float]:
        """Ensure embedding is non-empty."""
        if not v:
            raise ValueError("Embedding must not be empty.")
        return v

    @classmethod
    def from_numpy(
        cls,
        *,
        chunk_id: str,
        document_id: str,
        file_name: str,
        page_number: int,
        text: str,
        embedding: "np.ndarray",
        access_group: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ChunkUpsert":
        """Convenience constructor that accepts a numpy array for the embedding."""
        return cls(
            chunk_id=chunk_id,
            document_id=document_id,
            file_name=file_name,
            page_number=page_number,
            text=text,
            embedding=embedding.tolist(),
            access_group=access_group,
            metadata=metadata or {},
        )


class SearchQuery(BaseModel):
    """Input parameters for a vector similarity search."""

    query_vec: List[float] = Field(..., description="L2-normalised query embedding.")
    user_groups: List[str] = Field(..., min_length=1, description="Access-groups the caller belongs to.")
    top_k: int = Field(default=10, ge=1, le=200, description="Maximum number of results to return.")

    @classmethod
    def from_numpy(
        cls,
        query_vec: "np.ndarray",
        user_groups: List[str],
        top_k: int = 10,
    ) -> "SearchQuery":
        """Convenience constructor that accepts a numpy array."""
        return cls(query_vec=query_vec.tolist(), user_groups=user_groups, top_k=top_k)
