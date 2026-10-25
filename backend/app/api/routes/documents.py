"""
documents.py -- Document management and upload endpoints.

Allows listing accessible documents and uploading new PDFs, PPTXs, TXTs, or MD files
directly from the frontend interface.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status

from app.api.deps import get_current_user  # type: ignore[import]
from app.ingestion.pipeline import ingestion_pipeline  # type: ignore[import]

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", summary="Upload and index a document directly from the frontend")
async def upload_document(
    file: UploadFile = File(...),
    access_group: str = Form("general"),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload a PDF, PPTX, TXT, or MD file and index it into pgvector."""
    uploads_dir = "/tmp/uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    temp_path = os.path.join(uploads_dir, file.filename)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_id = hashlib.sha256(f"{file.filename}:{os.path.getsize(temp_path)}".encode()).hexdigest()[:32]

        stats = await ingestion_pipeline.ingest_file(
            file_path=temp_path,
            file_id=file_id,
            file_name=file.filename,
            access_group=access_group,
            source="upload",
        )

        if stats.get("errors"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to ingest {file.filename}: {'; '.join(stats['errors'])}",
            )

        return {
            "status": "success",
            "file_name": file.filename,
            "access_group": access_group,
            "chunks_created": stats.get("chunks_created", 0),
            "pages_parsed": stats.get("pages_parsed", 0),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {exc}",
        ) from exc
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@router.get("/documents", summary="List documents visible to the current user")
async def list_documents(
    current_user: dict = Depends(get_current_user),
) -> List[dict[str, Any]]:
    """
    Return all documents the authenticated user is allowed to see.

    Access groups are taken exclusively from the verified JWT -- they are
    never accepted as query parameters to prevent privilege escalation.

    Returns:
        List of document dicts sorted by indexed_at descending:
          file_name, access_group, indexed_at, chunk_count, source
    """
    user_groups: List[str] = current_user.get("groups", [])

    if not user_groups:
        return []

    try:
        from app.vector_store.pgvector_store import get_vector_store  # type: ignore[import]
        store = await get_vector_store()
        docs = await store.get_documents_by_groups(user_groups)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to query document store: {exc}",
        ) from exc

    # Sort by indexed_at descending (most recently indexed first)
    docs.sort(
        key=lambda d: d.get("indexed_at") or "",
        reverse=True,
    )

    return docs
