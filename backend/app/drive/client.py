"""
client.py — Google Drive API client using a service account.

Supports two modes for providing credentials:
  1. GOOGLE_SERVICE_ACCOUNT_JSON is a file path -> read JSON from disk.
  2. GOOGLE_SERVICE_ACCOUNT_JSON is the raw JSON string -> parse directly.

This lets the secret be injected as an environment variable in container
deployments without needing to mount a separate credentials file.

Handles pagination transparently (pageToken loop) for large folder listings.
Downloads both PDF and PPTX mime-types; silently skips unsupported types.
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

_PDF_MIME = "application/pdf"
_PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_SUPPORTED_MIMES = {_PDF_MIME, _PPTX_MIME}

_MIME_TO_EXT = {
    _PDF_MIME: ".pdf",
    _PPTX_MIME: ".pptx",
}


@dataclass
class DriveFile:
    """Metadata record for a Google Drive file.

    Attributes:
        id:           Drive file ID (unique, stable across renames).
        name:         Human-readable filename.
        mimeType:     MIME type string.
        modifiedTime: Last-modified timestamp (UTC, timezone-aware).
        trashed:      True if the file has been moved to the bin.
        parents:      List of parent folder IDs.
    """

    id: str
    name: str
    mimeType: str
    modifiedTime: datetime
    trashed: bool = False
    parents: List[str] = field(default_factory=list)


def get_drive_service():
    """Build and return an authenticated Google Drive v3 service object.

    Credentials are read from the GOOGLE_SERVICE_ACCOUNT_JSON environment
    variable (either a file path or raw JSON string).

    Returns:
        A ``googleapiclient.discovery.Resource`` for the Drive v3 API.

    Raises:
        RuntimeError: If the env var is not set or credentials are invalid.
    """
    from google.oauth2 import service_account  # type: ignore
    from googleapiclient.discovery import build  # type: ignore

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set."
        )

    # Determine if it's a file path or inline JSON
    if os.path.exists(raw):
        with open(raw, "r", encoding="utf-8") as fh:
            creds_info = json.load(fh)
    else:
        try:
            creds_info = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON is neither a valid file path "
                f"nor valid JSON: {exc}"
            ) from exc

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=scopes
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    logger.debug("Google Drive service built successfully.")
    return service


def list_modified_files(
    since: datetime,
    folder_id: str,
    service=None,
) -> List[DriveFile]:
    """List all files in *folder_id* modified after *since*.

    Paginates automatically using pageToken until all results are fetched.
    Only returns files with supported MIME types (PDF, PPTX).

    Args:
        since:     UTC-aware datetime; only files with modifiedTime > since
                   are returned.
        folder_id: Google Drive folder ID to scope the search.
        service:   Optional pre-built Drive service (created via
                   :func:`get_drive_service` if not provided).

    Returns:
        List of :class:`DriveFile` objects.
    """
    if service is None:
        service = get_drive_service()

    since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
    mime_filter = " or ".join(
        f"mimeType = '{m}'" for m in _SUPPORTED_MIMES
    )
    query = (
        f"'{folder_id}' in parents"
        f" and modifiedTime > '{since_str}'"
        f" and ({mime_filter})"
        f" and trashed = false"
    )

    files: List[DriveFile] = []
    page_token: Optional[str] = None

    while True:
        kwargs = {
            "q": query,
            "pageSize": 100,
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, trashed, parents)",
            "orderBy": "modifiedTime desc",
        }
        if page_token:
            kwargs["pageToken"] = page_token

        response = service.files().list(**kwargs).execute()

        for item in response.get("files", []):
            try:
                mod_time_str: str = item["modifiedTime"]
                # Drive API returns RFC-3339 strings like "2024-01-15T12:30:00.000Z"
                mod_time = datetime.fromisoformat(
                    mod_time_str.replace("Z", "+00:00")
                )
                files.append(
                    DriveFile(
                        id=item["id"],
                        name=item["name"],
                        mimeType=item["mimeType"],
                        modifiedTime=mod_time,
                        trashed=item.get("trashed", False),
                        parents=item.get("parents", []),
                    )
                )
            except Exception as exc:
                logger.warning("Skipping malformed file record: %s — %s", item, exc)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    logger.info(
        "Found %d modified files in folder '%s' since %s.",
        len(files),
        folder_id,
        since_str,
    )
    return files


def download_file(file_id: str, dest_path: str, service=None) -> str:
    """Download a Drive file to *dest_path* (or a temp file if dest_path is empty).

    Args:
        file_id:   Google Drive file ID.
        dest_path: Absolute local path to write the downloaded bytes to.
                   If the file's MIME type has a known extension and dest_path
                   lacks one, the extension is appended automatically.
        service:   Optional pre-built Drive service.

    Returns:
        The final local path where the file was written.

    Raises:
        RuntimeError: If the download fails.
    """
    from googleapiclient.http import MediaIoBaseDownload  # type: ignore

    if service is None:
        service = get_drive_service()

    # Determine file extension from metadata
    meta = service.files().get(fileId=file_id, fields="name,mimeType").execute()
    mime = meta.get("mimeType", "")
    ext = _MIME_TO_EXT.get(mime, "")

    if dest_path:
        if ext and not dest_path.endswith(ext):
            dest_path = dest_path + ext
    else:
        fd, dest_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)

    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug(
                    "Downloading '%s': %.0f%%",
                    meta.get("name", file_id),
                    status.progress() * 100,
                )

    logger.info(
        "Downloaded Drive file '%s' -> '%s' (%d bytes).",
        file_id,
        dest_path,
        os.path.getsize(dest_path),
    )
    return dest_path
