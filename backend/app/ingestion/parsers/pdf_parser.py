"""
pdf_parser.py — PDF document parser for the ingestion pipeline.

Primary strategy: use unstructured.partition.pdf which handles complex layouts,
multi-column text, embedded tables, and scanned PDFs (via OCR if available).

Fallback strategy: pdfplumber, which provides reliable text and table extraction
for well-formed PDFs without requiring system-level OCR dependencies.

Both strategies produce one ParsedPage per PDF page.  Tables are extracted and
appended to the page text as markdown-style plain text for downstream chunking.

Encrypted or corrupt pages are caught, logged as warnings, and skipped so a
single bad page does not abort ingestion of the entire document.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional

from app.ingestion.parsers.base_parser import BaseParser, ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)


def _table_to_markdown(table: list) -> str:
    """Convert a pdfplumber table (list of lists) to a markdown table string."""
    if not table:
        return ""
    rows: List[str] = []
    for i, row in enumerate(table):
        cells = [str(c or "").replace("|", "/").strip() for c in row]
        rows.append("| " + " | ".join(cells) + " |")
        if i == 0:
            rows.append("|" + "|".join(["---"] * len(cells)) + "|")
    return "\n".join(rows)


def _parse_with_unstructured(file_path: str) -> List[ParsedPage]:
    """Parse PDF using the unstructured library (primary strategy).

    Returns a list of ParsedPage objects, one per page.
    Raises any exception so the caller can fall back to pdfplumber.
    """
    from unstructured.partition.pdf import partition_pdf  # type: ignore

    elements = partition_pdf(filename=file_path, strategy="fast")

    # Group elements by page number
    pages_text: dict[int, list[str]] = {}
    pages_tables: dict[int, list[str]] = {}

    for el in elements:
        page_num: int = (el.metadata.page_number or 1) - 1  # 0-indexed
        el_type = type(el).__name__

        if el_type == "Table":
            text_repr = el.metadata.text_as_html or str(el)
            pages_tables.setdefault(page_num, []).append(text_repr)
        else:
            text = str(el).strip()
            if text:
                pages_text.setdefault(page_num, []).append(text)

    all_pages = sorted(set(list(pages_text.keys()) + list(pages_tables.keys())))
    if not all_pages:
        return []

    result: List[ParsedPage] = []
    for page_num in range(max(all_pages) + 1):
        text = "\n\n".join(pages_text.get(page_num, []))
        tables = pages_tables.get(page_num, [])
        result.append(ParsedPage(page_number=page_num, text=text, tables=tables))
    return result


def _parse_with_pdfplumber(file_path: str) -> List[ParsedPage]:
    """Parse PDF using pdfplumber (fallback strategy).

    Returns a list of ParsedPage objects, one per page.
    Skips pages that raise exceptions (logs a warning per skipped page).
    """
    import pdfplumber  # type: ignore

    parsed_pages: List[ParsedPage] = []
    with pdfplumber.open(file_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            try:
                text: str = page.extract_text() or ""

                tables: List[str] = []
                for raw_table in page.extract_tables():
                    md = _table_to_markdown(raw_table)
                    if md:
                        tables.append(md)

                parsed_pages.append(
                    ParsedPage(
                        page_number=page_index,
                        text=text.strip(),
                        tables=tables,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "pdfplumber: skipping page %d of '%s' due to error: %s",
                    page_index,
                    file_path,
                    exc,
                )
    return parsed_pages


class PDFParser(BaseParser):
    """Parser for .pdf files.

    Tries unstructured first; falls back to pdfplumber on any failure.
    Running the blocking I/O in a thread-pool executor keeps the event-loop
    free for other coroutines.
    """

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a PDF file and return a ParsedDocument.

        Args:
            file_path: Absolute path to the PDF file.

        Returns:
            ParsedDocument with one ParsedPage per PDF page.

        Raises:
            FileNotFoundError: If file_path does not exist.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        file_name = Path(file_path).name
        loop = asyncio.get_event_loop()

        pages: List[ParsedPage] = []
        try:
            pages = await loop.run_in_executor(None, _parse_with_unstructured, file_path)
            logger.info("Parsed '%s' with unstructured (%d pages).", file_name, len(pages))
        except Exception as primary_exc:
            logger.warning(
                "unstructured failed for '%s' (%s); falling back to pdfplumber.",
                file_name,
                primary_exc,
            )
            try:
                pages = await loop.run_in_executor(None, _parse_with_pdfplumber, file_path)
                logger.info(
                    "Parsed '%s' with pdfplumber (%d pages).", file_name, len(pages)
                )
            except Exception as fallback_exc:
                logger.error(
                    "Both parsers failed for '%s': %s", file_name, fallback_exc
                )
                raise

        # Merge table text into page text for downstream chunking
        final_pages: List[ParsedPage] = []
        for p in pages:
            combined_text = p.text
            if p.tables:
                combined_text = (combined_text + "\n\n" + "\n\n".join(p.tables)).strip()
            final_pages.append(
                ParsedPage(
                    page_number=p.page_number,
                    text=combined_text,
                    tables=p.tables,
                )
            )

        return ParsedDocument(
            file_name=file_name,
            source="local",  # caller may override after construction
            file_id=file_path,  # caller replaces with actual Drive ID
            access_group="",  # caller sets this
            pages=final_pages,
        )
