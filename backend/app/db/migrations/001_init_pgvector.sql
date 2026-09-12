-- 001_init_pgvector.sql
-- Bootstrap SQL run by the postgres container on first startup.
-- Enables the vector and uuid-ossp extensions, then creates performance
-- indexes and row-level security policies for the RAG schema.

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── HNSW index on chunk embeddings ───────────────────────────────────────────
-- Uses cosine distance (vector_cosine_ops) matching the BGE model metric.
-- m=16 / ef_construction=64 gives good recall / build-time tradeoff.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'chunks' AND indexname = 'idx_chunks_embedding_hnsw'
  ) THEN
    CREATE INDEX idx_chunks_embedding_hnsw
      ON chunks
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64);
  END IF;
END;
$$;

-- ── Access-group indexes ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_chunks_access_group
  ON chunks (access_group);

CREATE INDEX IF NOT EXISTS idx_documents_access_group
  ON documents (access_group);

-- ── Row-level security on query_logs ─────────────────────────────────────────
ALTER TABLE query_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS query_logs_user_isolation ON query_logs;

CREATE POLICY query_logs_user_isolation
  ON query_logs
  FOR ALL
  USING (user_id = current_setting('app.current_user_id', true));
