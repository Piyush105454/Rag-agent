"""
pgvector_store.py — Async PGVectorStore using asyncpg + pgvector.

Uses raw asyncpg queries rather than SQLAlchemy ORM because pgvector operators
(<=> cosine distance) and array casts are not cleanly supported by the ORM
layer without significant boilerplate.

Schema expected (created by Alembic migrations):
    CREATE TABLE chunks (
        chunk_id     UUID PRIMARY KEY,
        document_id  UUID NOT NULL,
        file_name    TEXT NOT NULL,
        page_number  INTEGER NOT NULL,
        text         TEXT NOT NULL,
        embedding    VECTOR(384) NOT NULL,
        access_group TEXT NOT NULL,
        metadata     JSONB NOT NULL DEFAULT '{}',
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
    CREATE INDEX ON chunks (access_group);
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg

from app.core.config import settings
from app.vector_store.schemas import ChunkUpsert, SearchResult

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


class PGVectorStore:
    """Async vector store backed by PostgreSQL + pgvector.

    Lifecycle:
        store = PGVectorStore()
        await store.connect()   # call once at app startup
        ...
        await store.close()     # call at app shutdown
    """

    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Create the asyncpg connection pool and register pgvector codec."""
        self._pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        # Register the vector type codec so asyncpg can parse VECTOR columns.
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await self._register_vector_codec(conn)
        logger.info("PGVectorStore connected (pool min=2, max=10).")

    async def close(self) -> None:
        """Close the connection pool gracefully."""
        if self._pool:
            await self._pool.close()
            logger.info("PGVectorStore pool closed.")

    @staticmethod
    async def _register_vector_codec(conn: asyncpg.Connection) -> None:
        """Register custom encode/decode for the pgvector 'vector' type."""
        await conn.execute("SET search_path TO public")
        # Fetch the OID of the 'vector' type
        vector_oid = await conn.fetchval(
            "SELECT oid FROM pg_type WHERE typname = 'vector'"
        )
        if vector_oid is None:
            raise RuntimeError(
                "pgvector extension is not installed. "
                "Run: CREATE EXTENSION vector; in your database."
            )

        def encode_vector(value: List[float]) -> str:
            return "[" + ",".join(str(x) for x in value) + "]"

        def decode_vector(text: str) -> List[float]:
            return [float(x) for x in text.strip("[]").split(",")]

        conn.add_types([
            asyncpg.types.Type(
                oid=vector_oid,
                name="vector",
                schema="public",
                kind="base",
            )
        ])
        conn.set_type_codec(
            "vector",
            schema="public",
            encoder=encode_vector,
            decoder=decode_vector,
            format="text",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PGVectorStore.connect() has not been called.")
        return self._pool

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def upsert_chunks(self, chunks: List[ChunkUpsert]) -> None:
        """Insert or update chunks in the vector store.

        Uses INSERT ... ON CONFLICT (chunk_id) DO UPDATE so re-ingesting the
        same chunk_id is idempotent (last-writer-wins on embedding & text).

        Args:
            chunks: List of ChunkUpsert objects to persist.
        """
        if not chunks:
            return

        sql = """
            INSERT INTO chunks
                (chunk_id, document_id, file_name, page_number, text,
                 embedding, access_group, metadata, updated_at)
            VALUES
                ($1, $2, $3, $4, $5, $6::vector, $7, $8::jsonb, NOW())
            ON CONFLICT (chunk_id) DO UPDATE SET
                document_id  = EXCLUDED.document_id,
                file_name    = EXCLUDED.file_name,
                page_number  = EXCLUDED.page_number,
                text         = EXCLUDED.text,
                embedding    = EXCLUDED.embedding,
                access_group = EXCLUDED.access_group,
                metadata     = EXCLUDED.metadata,
                updated_at   = NOW()
        """

        async with self.pool.acquire() as conn:
            for batch_start in range(0, len(chunks), _BATCH_SIZE):
                batch = chunks[batch_start: batch_start + _BATCH_SIZE]
                records = [
                    (
                        c.chunk_id,
                        c.document_id,
                        c.file_name,
                        c.page_number,
                        c.text,
                        "[" + ",".join(str(x) for x in c.embedding) + "]",
                        c.access_group,
                        json.dumps(c.metadata),
                    )
                    for c in batch
                ]
                await conn.executemany(sql, records)
                logger.debug("Upserted batch of %d chunks.", len(batch))

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def similarity_search(
        self,
        query_vec: List[float],
        user_groups: List[str],
        top_k: int = 10,
    ) -> List[SearchResult]:
        """Return the top-k most similar chunks visible to the user.

        Uses pgvector's <=> (cosine distance) operator and filters by
        access_group membership.  Score is converted to cosine *similarity*
        (1 - distance) so higher is better.

        Args:
            query_vec:   L2-normalised query embedding as a Python list.
            user_groups: Access-groups the requesting user belongs to.
            top_k:       Maximum number of results to return.

        Returns:
            List of SearchResult sorted descending by similarity score.
        """
        if not user_groups:
            return []

        vec_str = "[" + ",".join(str(x) for x in query_vec) + "]"

        sql = """
            SELECT
                chunk_id::text,
                document_id::text,
                file_name,
                page_number,
                text,
                1 - (embedding <=> $1::vector) AS score,
                access_group,
                metadata
            FROM chunks
            WHERE access_group = ANY($2::text[])
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, vec_str, user_groups, top_k)

        results: List[SearchResult] = []
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            results.append(
                SearchResult(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    file_name=row["file_name"],
                    page_number=row["page_number"],
                    text=row["text"],
                    score=float(row["score"]),
                    access_group=row["access_group"],
                    metadata=meta or {},
                )
            )
        return results

    async def delete_by_file_id(self, file_id: str) -> int:
        """Delete all chunks belonging to a document and return the count.

        Args:
            file_id: The document_id (UUID string) whose chunks to delete.

        Returns:
            Number of rows deleted.
        """
        sql = "DELETE FROM chunks WHERE document_id = $1::uuid RETURNING chunk_id"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, file_id)
        count = len(rows)
        logger.info("Deleted %d chunks for document_id=%s", count, file_id)
        return count

    async def get_documents_by_groups(self, groups: List[str]) -> List[Dict[str, Any]]:
        """Return distinct documents (files) visible to the given access groups.

        Args:
            groups: List of access-group strings the caller belongs to.

        Returns:
            List of dicts with keys: document_id, file_name, access_group, chunk_count.
        """
        if not groups:
            return []

        sql = """
            SELECT
                document_id::text,
                file_name,
                access_group,
                COUNT(*) AS chunk_count
            FROM chunks
            WHERE access_group = ANY($1::text[])
            GROUP BY document_id, file_name, access_group
            ORDER BY file_name
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, groups)

        return [
            {
                "document_id": row["document_id"],
                "file_name": row["file_name"],
                "access_group": row["access_group"],
                "chunk_count": row["chunk_count"],
            }
            for row in rows
        ]


# ---------------------------------------------------------------------------
# Module-level singleton (connected lazily via lifespan event in FastAPI)
# ---------------------------------------------------------------------------
vector_store = PGVectorStore()
