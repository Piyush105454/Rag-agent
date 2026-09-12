"""
poller.py — APScheduler-based background Drive sync scheduler.

Registers sync_drive() as an async interval job on the process-wide
AsyncIOScheduler.  max_instances=1 prevents overlapping runs if a sync
takes longer than the polling interval.

The scheduler is started once at application startup via start_drive_polling()
and is shut down gracefully when the FastAPI lifespan context exits.

trigger_sync_now() can be called from an admin API endpoint to run an
immediate out-of-cycle sync without restarting the scheduler.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore

from app.core.config import settings
from app.drive.sync import sync_drive

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None

JOB_ID = "drive_sync_job"


def get_scheduler() -> AsyncIOScheduler:
    """Return (or create) the process-wide APScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def start_drive_polling() -> AsyncIOScheduler:
    """Register sync_drive() as a recurring interval job and start the scheduler.

    The polling interval is read from settings.DRIVE_POLL_INTERVAL_MINUTES.
    max_instances=1 ensures that if one sync run is still executing when the
    next interval fires, the second invocation is silently skipped rather than
    running concurrently.

    Returns:
        The running AsyncIOScheduler instance (useful for testing/inspection).
    """
    scheduler = get_scheduler()

    if scheduler.get_job(JOB_ID):
        logger.info("Drive polling job already registered — skipping.")
        return scheduler

    scheduler.add_job(
        func=sync_drive,
        trigger=IntervalTrigger(minutes=settings.DRIVE_POLL_INTERVAL_MINUTES),
        id=JOB_ID,
        name="Google Drive Sync",
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=60,  # seconds; allow up to 60s late start
    )

    if not scheduler.running:
        scheduler.start()
        logger.info(
            "Drive polling started. Interval: %d min(s).",
            settings.DRIVE_POLL_INTERVAL_MINUTES,
        )
    else:
        logger.info("Scheduler already running; job added to existing scheduler.")

    return scheduler


def stop_drive_polling() -> None:
    """Shut down the scheduler gracefully (called on app shutdown)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Drive polling scheduler stopped.")
    _scheduler = None


async def trigger_sync_now() -> dict:
    """Immediately run a Drive sync outside the normal polling schedule.

    This is safe to call while the scheduler is running — it does not affect
    the regular interval timing.

    Returns:
        The sync stats dict from sync_drive().
    """
    logger.info("Manual Drive sync triggered.")
    return await sync_drive()
