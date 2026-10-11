"""
app/main.py

FastAPI application factory and entry point for the RAG backend.

Responsibilities:
  - Creates the FastAPI app with OpenAPI metadata.
  - Registers a lifespan context manager that (on startup) initialises the
    database, loads the embedding model into a shared app-state cache, and
    starts the APScheduler-based Google Drive / local-docs poller.
  - Mounts request-ID, logging, and CORS middleware.
  - Registers all API routers under their respective prefixes.
  - Provides a /health endpoint for Docker / load-balancer probes.
  - Exposes a uvicorn __main__ block for direct execution during development.

The embedding model is loaded once at startup and stored in
``app.state.embed_model`` so that all request handlers share the same
in-memory model without reloading it per-request.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv(".env")
load_dotenv("../.env")

import logging
import logging.config
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.middleware import LoggingMiddleware, RequestIDMiddleware, configure_cors
from app.config import settings
from app.db.session import init_db

# ── Logging configuration ──────────────────────────────────────────────────────
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)-8s %(name)s | %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            }
        },
        "root": {"level": "INFO", "handlers": ["console"]},
        "loggers": {
            "uvicorn.error": {"propagate": True},
            "uvicorn.access": {"propagate": False},  # silenced; LoggingMiddleware handles it
            "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
        },
    }
)

logger = logging.getLogger(__name__)

# ── Scheduler singleton ────────────────────────────────────────────────────────
_scheduler: AsyncIOScheduler | None = None


def _get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


# ── Drive / local poller ───────────────────────────────────────────────────────

async def _poll_drive() -> None:
    """Scheduled task: sync new/changed files from Google Drive."""
    if not settings.drive_sync_enabled:
        return
    try:
        # Import lazily to avoid startup cost when Drive is disabled
        from app.ingestion.drive_sync import sync_drive  # type: ignore[import]
        await sync_drive()
    except Exception as exc:
        logger.error("Drive sync failed: %s", exc, exc_info=True)


async def _poll_local() -> None:
    """Scheduled task: re-index any changed files in LOCAL_DOCS_PATH."""
    try:
        from app.ingestion.local_sync import sync_local  # type: ignore[import]
        await sync_local()
    except Exception as exc:
        logger.error("Local sync failed: %s", exc, exc_info=True)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Async lifespan context manager.

    Startup tasks:
      1. Initialise database tables (idempotent).
      2. Load the embedding model and store in app.state so route handlers
         can access it without re-instantiating.
      3. Start the APScheduler with Drive and local-docs polling jobs.

    Shutdown tasks:
      1. Shut down the scheduler gracefully.
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("=== RAG backend starting up ===")

    # 1. Database
    logger.info("Initialising database…")
    await init_db()

    # 2. Embedding model
    logger.info(
        "Loading embedding model %s on device=%s…",
        settings.embed_model,
        settings.embed_device,
    )
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]
        embed_model = SentenceTransformer(
            settings.embed_model, device=settings.embed_device
        )
        app.state.embed_model = embed_model
        logger.info("Embedding model loaded successfully.")
    except Exception as exc:
        logger.error("Failed to load embedding model: %s", exc, exc_info=True)
        app.state.embed_model = None

    # 3. Scheduler
    scheduler = _get_scheduler()
    interval_minutes = settings.drive_poll_interval_minutes

    scheduler.add_job(
        _poll_drive,
        trigger="interval",
        minutes=interval_minutes,
        id="drive_sync",
        replace_existing=True,
        misfire_grace_time=120,
    )
    scheduler.add_job(
        _poll_local,
        trigger="interval",
        minutes=interval_minutes,
        id="local_sync",
        replace_existing=True,
        misfire_grace_time=120,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — polling every %d minutes.", interval_minutes
    )

    logger.info("=== RAG backend ready ===")

    yield  # ── Application running ──────────────────────────────────────────

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("=== RAG backend shutting down ===")
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """
    Construct and configure the FastAPI application instance.

    Separated from module-level instantiation so the factory can be called
    in tests with different settings without global side-effects.
    """
    app = FastAPI(
        title="RAG Knowledge Assistant",
        description=(
            "A production-grade Retrieval-Augmented Generation API "
            "with access-group based document isolation, streaming answers, "
            "and MCP tool integration."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost wraps innermost) ──────────────────
    # RequestID must come before Logging so the ID is available when logging.
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    configure_cors(app)  # Adds CORSMiddleware

    # ── Routers ───────────────────────────────────────────────────────────────
    # Each router is registered lazily here; the actual route files are built
    # by other agents.  The try/except allows the app to start even when
    # those modules are not yet present (during iterative development).

    try:
        from app.api.routes.query import router as query_router  # type: ignore[import]
        app.include_router(query_router, tags=["Query"])
    except ImportError:
        logger.warning("query router not available yet.")

    try:
        from app.api.routes.documents import router as documents_router  # type: ignore[import]
        app.include_router(documents_router, tags=["Documents"])
    except ImportError:
        logger.warning("documents router not available yet.")

    try:
        from app.api.routes.auth import router as auth_router  # type: ignore[import]
        app.include_router(auth_router, tags=["Auth"])
    except ImportError:
        logger.warning("auth router not available yet.")

    # ── Health endpoint ────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health() -> JSONResponse:
        """
        Returns 200 OK when the application is running.
        Used by Docker healthcheck and load balancers.
        """
        embed_ready = getattr(app.state, "embed_model", None) is not None
        return JSONResponse(
            content={
                "status": "ok",
                "embed_model_loaded": embed_ready,
                "version": "1.0.0",
            }
        )

    return app


# ── Module-level app instance ─────────────────────────────────────────────────
# Uvicorn imports this directly: ``uvicorn app.main:app``
app: FastAPI = create_app()


# ── Development entrypoint ────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
