"""
file_tracker.py — DB-backed tracking of ingested files.

Maintains metadata about which files have been ingested into the system,
their access groups, and last-sync timestamps.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.db.session import get_pool

logger = logging.getLogger(__name__)


async def record_file(
    doc_id: str | UUID,
    file_id: str,
    file_name: str,
    access_group: str,
    source: str,
    chunk_count: int = 0,
    modified_time: Optional[datetime] = None,
) -> None:
    """Upsert a document row.

    Args:
        doc_id:        Primary key UUID for the document row.
        file_id:       Unique identifier for the file (Drive ID or hash).
        file_name:     Human-readable filename.
        access_group:  Access-group string.
        source:        'drive' or 'local'.
        chunk_count:   Number of chunks.
        modified_time: Optional last-modified timestamp from Google Drive.
    """
    uid = UUID(str(doc_id))
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO documents
                (id, file_id, file_name, access_group, source, chunk_count, modified_time, indexed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (file_id) DO UPDATE SET
                file_name     = EXCLUDED.file_name,
                access_group  = EXCLUDED.access_group,
                source        = EXCLUDED.source,
                chunk_count   = EXCLUDED.chunk_count,
                modified_time = EXCLUDED.modified_time,
                indexed_at    = NOW()
            """,
            uid,
            file_id,
            file_name,
            access_group,
            source,
            chunk_count,
            modified_time,
        )

    logger.info(
        "Recorded file '%s' (%s) with %d chunks.", file_name, file_id, chunk_count
    )


async def get_tracked_files() -> List[Dict[str, Any]]:
    """Return all tracked documents."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id::text AS document_id,
                file_id,
                file_name,
                access_group,
                source,
                modified_time,
                indexed_at,
                chunk_count
            FROM documents
            ORDER BY indexed_at DESC
            """
        )
    return [dict(row) for row in rows]


async def remove_file(file_id: str) -> None:
    """Delete a document record. Chunks are deleted via ON DELETE CASCADE."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM documents WHERE file_id = $1", file_id)

    logger.info("Removed file record '%s'.", file_id)


async def file_exists(file_id: str) -> bool:
    """Check whether a file has already been ingested."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT 1 FROM documents WHERE file_id = $1 LIMIT 1", file_id
        )
    return result is not None


async def update_modified_time(file_id: str, modified_time: datetime) -> None:
    """Update the stored last-modified timestamp for a file."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET modified_time = $1 WHERE file_id = $2",
            modified_time,
            file_id,
        )
    logger.debug("Updated modified_time for file '%s'.", file_id)
