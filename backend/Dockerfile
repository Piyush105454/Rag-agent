# backend/Dockerfile
# Multi-stage build for the RAG backend.
# Stage 1 (builder): installs Python dependencies into a venv.
# Stage 2 (runtime): copies the venv and app code, adds system-level document
# parsing tools (poppler, tesseract, libreoffice) needed by unstructured.

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time tools needed to compile Python C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create isolated venv so we can copy it cleanly into the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# System dependencies required at runtime:
#   libmagic1        - file type detection (unstructured)
#   poppler-utils    - PDF rendering / pdftotext (pdfplumber + unstructured)
#   tesseract-ocr    - OCR fallback for scanned PDFs
#   libreoffice      - PPTX / DOCX conversion to PDF for unstructured
#   curl             - Docker healthcheck probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    libreoffice \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Make app package importable from the /app root
ENV PYTHONPATH=/app

# Copy application source
COPY . .

# Ensure start script is executable
RUN chmod +x /app/start.sh

EXPOSE 8000 8001

CMD ["/app/start.sh"]
