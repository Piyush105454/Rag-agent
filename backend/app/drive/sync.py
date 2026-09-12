"""
sync.py — Google Drive sync orchestrator.

sync_drive():
  Reads the last-sync timestamp from the SyncState table (defaults to 30 days
  ago on first run), fetches all modified files from Drive since that time,
  and either ingests or deletes them depending on whether they are trashed.
  After processing all files, it updates SyncState.last_sync_time.

sync_local_folder():
  One-shot ingestion of an entire local directory — useful for bootstrapping
  the knowledge base before Drive integration is configured.

Expected schema (created by Alembic):
    CREATE TABLE sync_state (
        id            INTEGER PRIMARY KEY DEFAULT 1,
        folder_id     TEXT NOT NULL,
        last_sync_time TIMESTAMPTZ NOT NULL,
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT single_row CHECK (id = 1)
    );
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.config import settings
from app.db.session import get_pool
from app.drive import client as drive_client
from app.ingestion import file_tracker
from app.ingestion.pipeline import ingestion_pipeline
from app.vector_store.pgvector_store import vector_store

logger = logging.getLogger(__name__)

_DEFAULT_LOOKBACK_DAYS = 30


async def _get_last_sync_time(folder_id: str) -> datetime:
    """Fetch last sync time from DB; return 30 days ago if no record exists."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT last_sync_time FROM sync_state WHERE folder_id = $1",
            folder_id,
        )
    if row:
        return row["last_sync_time"]
    return datetime.now(timezone.utc) - timedelta(days=_DEFAULT_LOOKBACK_DAYS)


async def _update_last_sync_time(folder_id: str, sync_time: datetime) -> None:
    """Upsert the sync timestamp in the sync_state table."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sync_state (id, folder_id, last_sync_time, updated_at)
            VALUES (1, $1, $2, NOW())
            ON CONFLICT (id) DO UPDATE SET
                folder_id      = EXCLUDED.folder_id,
                last_sync_time = EXCLUDED.last_sync_time,
                updated_at     = NOW()
            """,
            folder_id,
            sync_time,
        )


async def sync_drive(
    folder_id: Optional[str] = None,
    access_group: Optional[str] = None,
) -> Dict[str, Any]:
    """Synchronise Google Drive with the local vector store.

    Steps:
    1. Load last-sync timestamp from SyncState (default: 30 days ago).
    2. List all Drive files modified since then.
    3. For trashed files: delete their chunks and document record.
       For live files: download to /tmp, ingest, delete /tmp file.
    4. Update SyncState.last_sync_time to now.

    Args:
        folder_id:    Drive folder ID to sync (falls back to
                      settings.DRIVE_FOLDER_ID if not provided).
        access_group: Access group for newly ingested files (falls back to
                      settings.DRIVE_ACCESS_GROUP).

    Returns:
        Stats dict: {ingested, deleted, errors, duration_seconds}
    """
    folder_id = folder_id or settings.DRIVE_FOLDER_ID
    access_group = access_group or settings.DRIVE_ACCESS_GROUP

    sync_start = datetime.now(timezone.utc)
    stats: Dict[str, Any] = {
        "ingested": 0,
        "deleted": 0,
        "errors": [],
        "duration_seconds": 0.0,
    }

    logger.info("Drive sync started for folder '%s'.", folder_id)

    try:
        last_sync = await _get_last_sync_time(folder_id)
        logger.info("Fetching Drive files modified since %s.", last_sync.isoformat())

        loop = asyncio.get_event_loop()
        drive_files = await loop.run_in_executor(
            None,
            drive_client.list_modified_files,
            last_sync,
            folder_id,
            None,  # service — built inside list_modified_files
        )

        logger.info("Found %d Drive file(s) to process.", len(drive_files))

        for drive_file in drive_files:
            try:
                if drive_file.trashed:
                    # Delete from vector store and tracker
                    old_chunk_ids = await file_tracker.remove_file(drive_file.id)
                    if old_chunk_ids:
                        await vector_store.delete_by_file_id(drive_file.id)
                    logger.info("Deleted trashed file '%s'.", drive_file.name)
                    stats["deleted"] += 1
                else:
                    # Download to temp file
                    tmp_path = ""
                    try:
                        fd, tmp_path = tempfile.mkstemp()
                        os.close(fd)

                        tmp_path = await loop.run_in_executor(
                            None,
                            drive_client.download_file,
                            drive_file.id,
                            tmp_path,
                            None,
                        )

                        file_stats = await ingestion_pipeline.ingest_file(
                            file_path=tmp_path,
                            file_id=drive_file.id,
                            file_name=drive_file.name,
                            access_group=access_group,
                            source="drive",
                        )

                        # Persist modifiedTime for future change detection
                        await file_tracker.update_modified_time(
                            drive_file.id, drive_file.modifiedTime
                        )

                        if not file_stats["errors"]:
                            stats["ingested"] += 1
                        else:
                            stats["errors"].extend(file_stats["errors"])

                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)

            except Exception as exc:
                msg = f"Error processing '{drive_file.name}': {exc}"
                logger.exception(msg)
                stats["errors"].append(msg)

        # Update last sync time only after all files are processed
        await _update_last_sync_time(folder_id, sync_start)

    except Exception as exc:
        msg = f"Drive sync failed: {exc}"
        logger.exception(msg)
        stats["errors"].append(msg)

    stats["duration_seconds"] = round(
        (datetime.now(timezone.utc) - sync_start).total_seconds(), 2
    )
    logger.info("Drive sync complete: %s", stats)
    return stats


async def sync_local_folder(
    folder_path: str,
    access_group: str,
) -> Dict[str, Any]:
    """Ingest all supported files from a local directory.

    This is a one-shot operation, typically used to bootstrap the knowledge base.

    Args:
        folder_path:  Absolute path to the local directory to walk.
        access_group: Access-group string applied to all ingested documents.

    Returns:
        Stats dict: {files_processed, chunks_created, errors}
    """
    logger.info(
        "Starting local folder sync: path='%s', access_group='%s'.",
        folder_path,
        access_group,
    )
    return await ingestion_pipeline.ingest_directory(
        directory=folder_path,
        access_group=access_group,
    )
