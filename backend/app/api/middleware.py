"""
app/api/middleware.py

Custom ASGI middleware for the RAG backend.

Three pieces of middleware are defined here:

1. RequestIDMiddleware
   Attaches a unique ``X-Request-ID`` header to every response so that
   individual requests can be correlated across logs, metrics, and client
   error reports.

2. LoggingMiddleware
   Emits a structured log line for every request containing: method, path,
   status code, and wall-clock duration in milliseconds.  Uses the standard
   ``logging`` module so the output format is controlled by the root logger
   configuration rather than hard-coded print statements.

3. configure_cors (helper)
   Returns a starlette CORSMiddleware instance configured from
   settings.cors_origins_list.  Called in app.main during app construction.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Generates a UUID4 request ID and attaches it as ``X-Request-ID`` to the
    response headers.  If the client already sends an ``X-Request-ID`` header
    that value is echoed back unchanged, allowing end-to-end tracing.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Reuse client-supplied ID or generate a fresh one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store on request state so route handlers can access it if needed
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Emits one structured log record per HTTP request with:
      - HTTP method
      - URL path (no query string, to avoid logging sensitive params)
      - Response status code
      - Wall-clock duration in milliseconds
      - Request ID (from request state, set by RequestIDMiddleware)

    Log level is INFO for 2xx/3xx, WARNING for 4xx, ERROR for 5xx.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)

        request_id = getattr(request.state, "request_id", "-")
        status_code = response.status_code

        log_record = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": status_code,
            "duration_ms": duration_ms,
        }

        if status_code >= 500:
            logger.error("HTTP request: %s", log_record)
        elif status_code >= 400:
            logger.warning("HTTP request: %s", log_record)
        else:
            logger.info("HTTP request: %s", log_record)

        return response


def configure_cors(app: FastAPI) -> None:
    """
    Attach CORSMiddleware to the FastAPI application.

    Origins are read from ``settings.cors_origins_list`` (parsed from the
    ``CORS_ORIGINS`` environment variable).  Credentials are allowed so that
    the Next.js frontend can send the ``Authorization`` header in cross-origin
    requests.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
