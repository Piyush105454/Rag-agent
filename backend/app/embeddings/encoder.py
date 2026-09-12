"""
encoder.py — Singleton SentenceTransformer wrapper for text embedding.

Wraps BAAI/bge-small-en-v1.5 (384-dim) using the sentence-transformers library.
Device is controlled by the EMBED_DEVICE env-var (cpu | cuda), making it safe
to run on CPU in production while optionally accelerating on GPU in dev.

Embeddings are L2-normalised before returning so that cosine similarity equals
the dot product, compatible with pgvector's <=> (cosine-distance) operator.

The module-level singleton is created once at import time and reused across all
requests, avoiding repeated model loading which is expensive (~seconds).
"""

from __future__ import annotations

import logging
import threading
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_instance: "EmbeddingEncoder | None" = None


class EmbeddingEncoder:
    """Thread-safe wrapper around SentenceTransformer.

    Do not instantiate directly; use get_encoder() to obtain the singleton.
    """

    def __init__(self) -> None:
        logger.info(
            "Loading embedding model '%s' on device '%s'",
            settings.EMBED_MODEL,
            settings.EMBED_DEVICE,
        )
        self._model = SentenceTransformer(
            settings.EMBED_MODEL,
            device=settings.EMBED_DEVICE,
        )
        logger.info("Embedding model loaded successfully.")

    def encode(self, text: str) -> np.ndarray:
        """Encode a single string to a normalised float32 vector (384-dim).

        Args:
            text: Raw input string.

        Returns:
            1-D numpy array of shape (384,) with unit L2 norm.
        """
        vec: np.ndarray = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vec.astype(np.float32)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Encode a list of strings to a 2-D normalised float32 matrix.

        Args:
            texts: List of raw input strings.

        Returns:
            2-D numpy array of shape (N, 384) with unit L2 norm per row.
        """
        if not texts:
            dim = self._model.get_sentence_embedding_dimension()
            return np.empty((0, dim), dtype=np.float32)

        vecs: np.ndarray = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=64,
            show_progress_bar=False,
        )
        return vecs.astype(np.float32)

    @property
    def embedding_dim(self) -> int:
        """Return embedding dimensionality (384 for bge-small-en-v1.5)."""
        return self._model.get_sentence_embedding_dimension()  # type: ignore[return-value]


def get_encoder() -> EmbeddingEncoder:
    """Return (or lazily create) the process-wide EmbeddingEncoder singleton.

    Thread-safe: double-checked locking ensures model is loaded only once.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EmbeddingEncoder()
    return _instance


# Eagerly create the singleton so import-time errors surface immediately.
_encoder: EmbeddingEncoder = get_encoder()
