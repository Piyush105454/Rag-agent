"""
app/db/session.py

Async SQLAlchemy engine and session factory for the RAG backend.

Uses asyncpg as the database driver (specified in the asyncpg-dialect URL).
The module exposes:
  - `engine`       : the shared AsyncEngine instance
  - `AsyncSessionLocal` : the session factory
  - `get_db()`     : FastAPI dependency that yields a database session
  - `init_db()`    : async function that creates all ORM-mapped tables

pool_pre_ping=True ensures stale connections from the pool are detected and
recycled before use, which is important for long-running containerised apps.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)


# ── Declarative base shared by all ORM models ─────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models in this project."""


# ── Async engine ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=False,              # Set True for SQL query logging during debugging
    pool_pre_ping=True,      # Recycle stale connections before use
    pool_size=10,            # Connections kept open in the pool
    max_overflow=20,         # Extra connections allowed beyond pool_size
    pool_recycle=3600,       # Recycle connections after 1 hour to avoid timeouts
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent lazy-load errors after commit in async context
    autocommit=False,
    autoflush=False,
)


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async generator that yields a database session for use as a FastAPI
    dependency (``Depends(get_db)``).  The session is automatically closed
    (and the transaction rolled back on error) when the request finishes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Table initialisation ──────────────────────────────────────────────────────
async def init_db() -> None:
    """
    Create all tables defined by ORM models if they do not already exist.
    Called once during application startup via the lifespan context manager.

    NOTE: For production deployments with Alembic, use ``alembic upgrade head``
    instead of this function. This helper is retained for local development and
    test environments where Alembic is not being run.
    """
    # Import models here to ensure all mappers are registered with Base before
    # create_all is called.  Avoid circular imports by keeping this local.
    import app.db.models  # noqa: F401  (side-effect import)

    logger.info("Initialising database tables…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready.")


async def get_pool():
    """Return the shared asyncpg pool from the vector store."""
    from app.vector_store.pgvector_store import get_vector_store
    store = await get_vector_store()
    return store.pool

