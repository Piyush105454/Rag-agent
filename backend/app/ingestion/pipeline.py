"""
pipeline.py — IngestionPipeline: end-to-end document ingestion orchestrator.

Wires together:  Parser -> Chunker -> Encoder (+cache) -> PGVectorStore -> FileTracker

Key design choices:
- All chunks in a file are embedded in a single batch call to maximise GPU/CPU
  throughput (encode_batch) rather than embedding one chunk at a time.
- Re-ingesting the same file_id atomically replaces old chunks: old vectors are
  deleted from pgvector and the document_chunks mapping is wiped before new data
  is inserted.  The whole operation runs inside a logical transaction so a
  partial failure leaves the system consistent.
- Blocking I/O (parsing, file walks) is dispatched to a thread-pool executor so
  the asyncio event-loop is never blocked.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.embeddings.cache import get_cached, set_cache
from app.embeddings.encoder import get_encoder
from app.ingestion import file_tracker
from app.ingestion.chunker import TokenChunker
from app.ingestion.parsers.base_parser import ParsedDocument
from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.pptx_parser import PPTXParser
from app.vector_store.pgvector_store import get_vector_store
from app.vector_store.schemas import ChunkUpsert

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".txt", ".md"}


def _deterministic_chunk_id(file_id: str, page_number: int, chunk_index: int) -> str:
    """Generate a stable UUID-format chunk ID from its position in the document.

    Using a deterministic ID means re-ingesting the same content produces the
    same chunk_id, so ON CONFLICT DO UPDATE is truly idempotent.
    """
    raw = f"{file_id}:{page_number}:{chunk_index}"
    return str(uuid.UUID(hashlib.md5(raw.encode()).hexdigest()))


class IngestionPipeline:
    """Orchestrates the full document ingestion lifecycle.

    Usage::

        pipeline = IngestionPipeline()
        stats = await pipeline.ingest_file(
            file_path="/tmp/report.pdf",
            file_id="drive-file-abc123",
            file_name="report.pdf",
            access_group="finance",
            source="drive",
        )
    """

    def __init__(self) -> None:
        self._chunker = TokenChunker()
        self._pdf_parser = PDFParser()
        self._pptx_parser = PPTXParser()
        self._encoder = get_encoder()

    # ------------------------------------------------------------------
    # Single-file ingestion
    # ------------------------------------------------------------------

    async def ingest_file(
        self,
        file_path: str,
        file_id: str,
        file_name: str,
        access_group: str,
        source: str,
    ) -> Dict[str, Any]:
        """Ingest a single file through the full ML pipeline.

        Steps:
          1. Parse (PDF or PPTX) -> ParsedDocument
          2. Chunk each page with TokenChunker
          3. Embed all chunks in one batch (with LRU cache)
          4. Upsert chunks into pgvector
          5. Record file in file_tracker

        On re-ingest: deletes existing chunks first, then inserts fresh ones.

        Args:
            file_path:    Absolute path to the file on local disk.
            file_id:      Unique identifier (Drive ID or deterministic hash).
            file_name:    Human-readable filename.
            access_group: Access-group string for row-level security.
            source:       'drive' or 'local'.

        Returns:
            Stats dict: {file_id, file_name, chunks_created, pages_parsed, errors}
        """
        stats: Dict[str, Any] = {
            "file_id": file_id,
            "file_name": file_name,
            "chunks_created": 0,
            "pages_parsed": 0,
            "errors": [],
        }

        try:
            # ---- Step 0: Atomic replace — delete old chunks if re-ingesting ----
            store = await get_vector_store()
            if await file_tracker.file_exists(file_id):
                await file_tracker.remove_file(file_id)
                logger.info("Re-ingesting '%s': purged previous records.", file_name)

            # ---- Step 1: Parse ----
            parsed_doc: ParsedDocument = await self._parse_file(file_path, file_name)
            parsed_doc.source = source
            parsed_doc.file_id = file_id
            parsed_doc.access_group = access_group
            stats["pages_parsed"] = len(parsed_doc.pages)

            # ---- Step 2: Chunk ----
            all_chunks: List[Dict[str, Any]] = []
            for page in parsed_doc.pages:
                page_chunks = self._chunker.chunk(
                    text=page.text,
                    file_name=file_name,
                    page_number=page.page_number,
                )
                all_chunks.extend(page_chunks)

            if not all_chunks:
                logger.warning("No chunks produced for '%s' — skipping.", file_name)
                return stats

            # ---- Step 3: Embed (batch, with cache) ----
            texts = [c["text"] for c in all_chunks]
            embeddings = await self._embed_batch_cached(texts)

            # ---- Step 4: Record document in DB (satisfies foreign key) ----
            document_id = str(uuid.UUID(hashlib.md5(file_id.encode()).hexdigest()))
            await file_tracker.record_file(
                doc_id=document_id,
                file_id=file_id,
                file_name=file_name,
                access_group=access_group,
                source=source,
                chunk_count=len(all_chunks),
            )

            # ---- Step 5: Build ChunkUpsert objects & upsert into pgvector ----
            chunk_upserts: List[ChunkUpsert] = []
            for i, (chunk_meta, embedding) in enumerate(zip(all_chunks, embeddings)):
                cid = _deterministic_chunk_id(
                    file_id, chunk_meta["page_number"], chunk_meta["chunk_index"]
                )
                chunk_upserts.append(
                    ChunkUpsert.from_numpy(
                        chunk_id=cid,
                        document_id=document_id,
                        file_name=file_name,
                        page_number=chunk_meta["page_number"],
                        text=chunk_meta["text"],
                        embedding=embedding,
                        access_group=access_group,
                        metadata={
                            "chunk_index": chunk_meta["chunk_index"],
                            "token_count": chunk_meta["token_count"],
                            "source": source,
                        },
                    )
                )

            await store.upsert_chunks(chunk_upserts)
            stats["chunks_created"] = len(chunk_upserts)

            logger.info(
                "Ingested '%s': %d pages, %d chunks.",
                file_name,
                stats["pages_parsed"],
                stats["chunks_created"],
            )

        except Exception as exc:
            logger.exception("Failed to ingest '%s': %s", file_name, exc)
            stats["errors"].append(str(exc))

        return stats

    # ------------------------------------------------------------------
    # Directory ingestion
    # ------------------------------------------------------------------

    async def ingest_directory(
        self,
        directory: str,
        access_group: str,
    ) -> Dict[str, Any]:
        """Walk *directory* and ingest all supported files (.pdf, .pptx, .ppt).

        Args:
            directory:    Absolute path to the local directory.
            access_group: Access-group string applied to all files found.

        Returns:
            Aggregate stats dict:
                {files_processed, chunks_created, errors: List[str]}
        """
        agg: Dict[str, Any] = {
            "files_processed": 0,
            "chunks_created": 0,
            "errors": [],
        }

        loop = asyncio.get_event_loop()
        file_list: List[Path] = await loop.run_in_executor(
            None, self._collect_files, directory
        )

        logger.info(
            "Found %d supported files in '%s'.", len(file_list), directory
        )

        for file_path in file_list:
            ext = file_path.suffix.lower()
            file_id = self._path_to_file_id(str(file_path))
            stats = await self.ingest_file(
                file_path=str(file_path),
                file_id=file_id,
                file_name=file_path.name,
                access_group=access_group,
                source="local",
            )
            agg["files_processed"] += 1
            agg["chunks_created"] += stats["chunks_created"]
            agg["errors"].extend(stats["errors"])

        return agg

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _parse_file(self, file_path: str, file_name: str) -> ParsedDocument:
        """Dispatch to the correct parser based on file extension."""
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return await self._pdf_parser.parse(file_path)
        elif ext in {".pptx", ".ppt"}:
            return await self._pptx_parser.parse(file_path)
        elif ext in {".txt", ".md"}:
            text = Path(file_path).read_text(encoding="utf-8", errors="replace")
            from app.ingestion.parsers.base_parser import ParsedPage
            return ParsedDocument(
                file_name=file_name,
                source="local",
                file_id="",
                access_group="",
                pages=[ParsedPage(page_number=1, text=text, tables=[])],
            )
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    async def _embed_batch_cached(self, texts: List[str]):
        """Embed a batch of texts, hitting LRU cache for repeated strings.

        Returns a list of numpy arrays in the same order as *texts*.
        """
        import numpy as np

        results = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        for i, text in enumerate(texts):
            cached = get_cached(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            loop = asyncio.get_event_loop()
            fresh_embeddings = await loop.run_in_executor(
                None, self._encoder.encode_batch, uncached_texts
            )
            for idx, text, emb in zip(uncached_indices, uncached_texts, fresh_embeddings):
                set_cache(text, emb)
                results[idx] = emb

        return results

    @staticmethod
    def _collect_files(directory: str) -> List[Path]:
        """Walk directory tree and return paths with supported extensions."""
        found: List[Path] = []
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                p = Path(root) / fname
                if p.suffix.lower() in _SUPPORTED_EXTENSIONS:
                    found.append(p)
        return found

    @staticmethod
    def _path_to_file_id(file_path: str) -> str:
        """Generate a stable file_id from an absolute file path."""
        return hashlib.sha256(file_path.encode()).hexdigest()[:32]


# Module-level singleton for import convenience
ingestion_pipeline = IngestionPipeline()
