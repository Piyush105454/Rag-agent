#!/usr/bin/env bash
# scripts/ingest_local.sh
#
# Ingests all files in ./local_docs into the RAG backend vector store.
# Runs the ingestion pipeline inside the running backend Docker container.
#
# Prerequisites:
#   - docker-compose up -d has been run
#   - local_docs/ folder exists with documents (run seed_test_docs.py first)
#
# Usage:
#   bash scripts/ingest_local.sh
#   bash scripts/ingest_local.sh --group engineering  # override group

set -euo pipefail

CONTAINER_NAME="${CONTAINER:-backend}"
LOCAL_DOCS_DIR="${DOCS_DIR:-./local_docs}"
DEFAULT_GROUP="${1:-general}"

echo "=== RAG Local Ingestion ==="
echo "Container: $CONTAINER_NAME"
echo "Docs dir:  $LOCAL_DOCS_DIR"
echo "Group:     $DEFAULT_GROUP"
echo ""

# Check the container is running
if ! docker inspect "$CONTAINER_NAME" --format '{{.State.Status}}' 2>/dev/null | grep -q "running"; then
  echo "ERROR: Container '$CONTAINER_NAME' is not running."
  echo "  Run: docker-compose up -d"
  exit 1
fi

# Copy local_docs into the container
echo "Copying $LOCAL_DOCS_DIR into container..."
docker cp "$LOCAL_DOCS_DIR" "$CONTAINER_NAME:/app/local_docs"

# Ingest each group separately based on filename prefix
echo "Running ingestion pipeline..."
for GROUP in sales engineering general hr; do
  # Find files matching the group (loose convention: filename contains group name)
  FILES=$(docker exec "$CONTAINER_NAME" find /app/local_docs -name "*${GROUP}*" -type f 2>/dev/null || true)
  if [ -n "$FILES" ]; then
    echo "  Ingesting group: $GROUP"
    docker exec "$CONTAINER_NAME" \
      python -m app.ingestion.pipeline ingest /app/local_docs "$GROUP" \
      --pattern "*${GROUP}*"
  fi
done

# Ingest any remaining files under the default group
echo "  Ingesting remaining files under group: $DEFAULT_GROUP"
docker exec "$CONTAINER_NAME" \
  python -m app.ingestion.pipeline ingest /app/local_docs "$DEFAULT_GROUP"

echo ""
echo "Ingestion complete! Verify with:"
echo "  curl -H 'Authorization: Bearer <JWT>' http://localhost:8000/documents"
