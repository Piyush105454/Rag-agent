"""
cache.py — In-memory LRU cache for text embeddings.

Avoids re-embedding identical text fragments by storing their vectors keyed by
the SHA-256 hash of the text.  Uses an OrderedDict to implement LRU eviction
(move-to-end on hit, popitem(last=False) to evict oldest on overflow).

Max capacity: 10,000 entries.
All operations are protected by a threading.Lock so the cache is safe to use
from multiple async tasks running in the event-loop and thread-pool workers.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

_MAX_ENTRIES: int = 10_000

_cache: OrderedDict[str, np.ndarray] = OrderedDict()
_lock: threading.Lock = threading.Lock()
_hits: int = 0
_misses: int = 0


def _hash_text(text: str) -> str:
    """Return the SHA-256 hex digest of text (UTF-8 encoded)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_cached(text: str) -> Optional[np.ndarray]:
    """Look up text in the LRU cache.

    Args:
        text: The raw input string whose embedding you want.

    Returns:
        A copy of the cached numpy vector if found, else None.
    """
    global _hits, _misses
    key = _hash_text(text)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            _hits += 1
            return _cache[key].copy()
        _misses += 1
        return None


def set_cache(text: str, embedding: np.ndarray) -> None:
    """Store embedding for text in the LRU cache.

    If the cache is at capacity, the least-recently-used entry is evicted
    before the new one is inserted.

    Args:
        text:      The raw input string.
        embedding: Float32 numpy array (shape: (D,)).
    """
    key = _hash_text(text)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            _cache[key] = embedding.copy()
            return
        if len(_cache) >= _MAX_ENTRIES:
            evicted_key, _ = _cache.popitem(last=False)
            logger.debug("LRU eviction: key %s...", evicted_key[:8])
        _cache[key] = embedding.copy()


def cache_stats() -> Dict[str, object]:
    """Return a snapshot of cache performance metrics.

    Returns:
        dict with keys: size, max_size, hits, misses, hit_rate
    """
    with _lock:
        total = _hits + _misses
        return {
            "size": len(_cache),
            "max_size": _MAX_ENTRIES,
            "hits": _hits,
            "misses": _misses,
            "hit_rate": round(_hits / total, 4) if total else 0.0,
        }


def clear_cache() -> None:
    """Flush all cached entries and reset counters (useful in tests)."""
    global _hits, _misses
    with _lock:
        _cache.clear()
        _hits = 0
        _misses = 0
