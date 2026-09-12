"""
chunker.py — Token-based text chunker using tiktoken.

Splits document text into overlapping token windows suitable for embedding
and retrieval.  Uses cl100k_base encoding (same as GPT-4 / text-embedding-3)
for accurate token counting.

Strategy:
- Encode the full text to a token list.
- Slide a window of `target_tokens` across the list with an overlap of
  `overlap_tokens = ceil(target_tokens * overlap_ratio)` tokens.
- Texts shorter than target_tokens are returned as a single chunk.

Each chunk carries positional metadata (file_name, page_number, chunk_index)
that is stored alongside the vector in the DB for provenance tracking.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

import tiktoken

logger = logging.getLogger(__name__)

_ENCODING_NAME = "cl100k_base"


class TokenChunker:
    """Splits plain text into overlapping token windows.

    Args:
        target_tokens:  Desired number of tokens per chunk (default 650).
        overlap_ratio:  Fraction of target_tokens used as overlap (default 0.15
                        -> ~97 token overlap at target_tokens=650).
    """

    def __init__(
        self,
        target_tokens: int = 650,
        overlap_ratio: float = 0.15,
    ) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = math.ceil(target_tokens * overlap_ratio)
        self._enc = tiktoken.get_encoding(_ENCODING_NAME)
        logger.debug(
            "TokenChunker initialised: target=%d tokens, overlap=%d tokens.",
            self.target_tokens,
            self.overlap_tokens,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(
        self,
        text: str,
        file_name: str,
        page_number: int,
    ) -> List[Dict[str, Any]]:
        """Split *text* into overlapping token chunks.

        Args:
            text:        Plain text to split.
            file_name:   Source file name (stored in chunk metadata).
            page_number: Source page/slide number (0-indexed).

        Returns:
            List of dicts with keys:
                chunk_index (int)   — position of this chunk within the page
                text        (str)   — decoded chunk text
                token_count (int)   — number of tokens in this chunk
                file_name   (str)   — source file name
                page_number (int)   — source page/slide number
        """
        text = text.strip()
        if not text:
            return []

        tokens = self._enc.encode(text)
        n = len(tokens)

        # Short texts fit in a single chunk
        if n <= self.target_tokens:
            return [
                {
                    "chunk_index": 0,
                    "text": text,
                    "token_count": n,
                    "file_name": file_name,
                    "page_number": page_number,
                }
            ]

        chunks: List[Dict[str, Any]] = []
        step = self.target_tokens - self.overlap_tokens
        start = 0
        chunk_index = 0

        while start < n:
            end = min(start + self.target_tokens, n)
            chunk_tokens = tokens[start:end]
            chunk_text = self._enc.decode(chunk_tokens).strip()

            if chunk_text:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                        "token_count": len(chunk_tokens),
                        "file_name": file_name,
                        "page_number": page_number,
                    }
                )
                chunk_index += 1

            if end == n:
                break
            start += step

        logger.debug(
            "Chunked page %d of '%s': %d tokens -> %d chunks.",
            page_number,
            file_name,
            n,
            len(chunks),
        )
        return chunks
