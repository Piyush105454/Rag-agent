"""
file_tracker.py — Async DB-backed tracker for ingested documents.

Maintains two tables:
  - documents: one row per ingested file (file_id is the Drive ID or hash).
  - document_chunks: maps chunk_ids to their parent document.

This enables the sync system to:
  1. Detect whether a file has already been ingested (file_exists).
  2. Retrieve the chunk_ids that belong to a file so they can be deleted
     from pgvector before re-ingesting (remove_file).
  3. Track modified times so we can skip files that have not changed.

Uses the shared asyncpg pool from the database module.

Expected schema (created by Alembic):
    CREATE TABLE documents (
        file_id       TEXT PRIMARY KEY,
        file_name     TEXT NOT NULL,
        access_group  TEXT NOT NULL,
        source        TEXT NOT NULL,         -- 'drive' | 'local'
        modified_time TIMESTAMPTZ,
        ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE document_chunks (
        chunk_id   TEXT NOT NULL,
        file_id    TEXT NOT NULL REFERENCES documents(file_id) ON DELETE CASCADE,
        PRIMARY KEY (chunk_id, file_id)
    );
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.session import get_pool

logger = logging.getLogger(__name__)


async def record_file(
    file_id: str,
    file_name: str,
    access_group: str,
    source: str,
    chunk_ids: List[str],
    modified_time: Optional[datetime] = None,
) -> None:
    """Upsert a document row and persist its chunk_id mapping.

    Args:
        file_id:       Unique identifier for the file (Drive ID or hash).
        file_name:     Human-readable filename.
        access_group:  Access-group string.
        source:        'drive' or 'local'.
        chunk_ids:     List of chunk UUIDs (strings) created during ingestion.
        modified_time: Optional last-modified timestamp from Google Drive.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO documents
                    (file_id, file_name, access_group, source, modified_time, ingested_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (file_id) DO UPDATE SET
                    file_name     = EXCLUDED.file_name,
                    access_group  = EXCLUDED.access_group,
                    source        = EXCLUDED.source,
                    modified_time = EXCLUDED.modified_time,
                    ingested_at   = NOW()
                """,
                file_id,
                file_name,
                access_group,
                source,
                modified_time,
            )

            # Delete old chunk mappings before inserting fresh ones
            await conn.execute(
                "DELETE FROM document_chunks WHERE file_id = $1", file_id
            )

            if chunk_ids:
                await conn.executemany(
                    "INSERT INTO document_chunks (chunk_id, file_id) VALUES ($1, $2)",
                    [(cid, file_id) for cid in chunk_ids],
                )

    logger.info(
        "Recorded file '%s' (%s) with %d chunks.", file_name, file_id, len(chunk_ids)
    )


async def get_tracked_files() -> List[Dict[str, Any]]:
    """Return all tracked documents.

    Returns:
        List of dicts with keys: file_id, file_name, access_group, source,
        modified_time, ingested_at, chunk_count.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                d.file_id,
                d.file_name,
                d.access_group,
                d.source,
                d.modified_time,
                d.ingested_at,
                COUNT(dc.chunk_id) AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks dc ON dc.file_id = d.file_id
            GROUP BY d.file_id
            ORDER BY d.ingested_at DESC
            """
        )
    return [dict(row) for row in rows]


async def remove_file(file_id: str) -> List[str]:
    """Delete a document record and return the list of chunk_ids to purge.

    The document_chunks rows are deleted via ON DELETE CASCADE, so only the
    documents row needs to be explicitly removed.

    Args:
        file_id: The unique file identifier.

    Returns:
        List of chunk_id strings that should be deleted from the vector store.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Fetch chunk_ids before cascade-deleting them
        rows = await conn.fetch(
            "SELECT chunk_id FROM document_chunks WHERE file_id = $1", file_id
        )
        chunk_ids = [row["chunk_id"] for row in rows]

        await conn.execute("DELETE FROM documents WHERE file_id = $1", file_id)

    logger.info(
        "Removed file record '%s'; %d chunks queued for deletion.",
        file_id,
        len(chunk_ids),
    )
    return chunk_ids


async def file_exists(file_id: str) -> bool:
    """Check whether a file has already been ingested.

    Args:
        file_id: The unique file identifier.

    Returns:
        True if a document record with this file_id exists.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT 1 FROM documents WHERE file_id = $1 LIMIT 1", file_id
        )
    return result is not None


async def update_modified_time(file_id: str, modified_time: datetime) -> None:
    """Update the stored last-modified timestamp for a file.

    Used by the Drive sync loop after successfully re-ingesting a changed file.

    Args:
        file_id:       The unique file identifier.
        modified_time: New last-modified timestamp from Google Drive.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET modified_time = $1 WHERE file_id = $2",
            modified_time,
            file_id,
        )
    logger.debug("Updated modified_time for file '%s'.", file_id)
