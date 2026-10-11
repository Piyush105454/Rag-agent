"""
pptx_parser.py — PowerPoint (PPTX) parser for the ingestion pipeline.

Primary strategy: unstructured.partition.pptx — handles embedded images,
complex layouts, and SmartArt gracefully.

Fallback strategy: python-pptx — lightweight, no C dependencies, reliably
extracts text frames and table cells from standard PPTX files.

One ParsedPage is produced per slide.  Speaker notes are appended to the slide
text so they are included in the semantic index.  Tables are extracted as
markdown-style plain text.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List

from app.ingestion.parsers.base_parser import BaseParser, ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)


def _table_cells_to_markdown(table) -> str:
    """Convert a python-pptx Table object to a markdown table string."""
    rows: List[str] = []
    for row_idx, row in enumerate(table.rows):
        cells = [cell.text.strip().replace("|", "/") for cell in row.cells]
        rows.append("| " + " | ".join(cells) + " |")
        if row_idx == 0:
            rows.append("|" + "|".join(["---"] * len(cells)) + "|")
    return "\n".join(rows)


def _parse_with_unstructured(file_path: str) -> List[ParsedPage]:
    """Parse PPTX using the unstructured library (primary strategy)."""
    from unstructured.partition.pptx import partition_pptx  # type: ignore

    elements = partition_pptx(filename=file_path)

    pages_text: dict[int, list[str]] = {}
    pages_tables: dict[int, list[str]] = {}

    for el in elements:
        # unstructured uses 1-based page numbers
        page_num: int = (el.metadata.page_number or 1) - 1
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


def _parse_with_python_pptx(file_path: str) -> List[ParsedPage]:
    """Parse PPTX using python-pptx (fallback strategy).

    Extracts:
    - Text frames from all shapes on the slide.
    - Table cells from table shapes.
    - Speaker notes (notes placeholder text).
    """
    from pptx import Presentation  # type: ignore
    from pptx.util import Pt  # type: ignore
    from pptx.enum.shapes import MSO_SHAPE_TYPE  # type: ignore

    prs = Presentation(file_path)
    parsed_pages: List[ParsedPage] = []

    for slide_idx, slide in enumerate(prs.slides):
        text_parts: List[str] = []
        tables: List[str] = []

        for shape in slide.shapes:
            try:
                # Extract text frames
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        para_text = " ".join(run.text for run in para.runs).strip()
                        if para_text:
                            text_parts.append(para_text)

                # Extract tables
                if shape.has_table:
                    md = _table_cells_to_markdown(shape.table)
                    if md:
                        tables.append(md)
            except Exception as exc:
                logger.debug(
                    "python-pptx: skipping shape on slide %d: %s", slide_idx, exc
                )

        # Extract speaker notes
        try:
            notes_slide = slide.notes_slide
            if notes_slide and notes_slide.notes_text_frame:
                notes_text = notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    text_parts.append(f"[Notes]: {notes_text}")
        except Exception:
            pass

        parsed_pages.append(
            ParsedPage(
                page_number=slide_idx,
                text="\n\n".join(text_parts),
                tables=tables,
            )
        )

    return parsed_pages


class PPTXParser(BaseParser):
    """Parser for .pptx/.ppt files.

    Tries unstructured first; falls back to python-pptx on any failure.
    Blocking I/O runs in a thread-pool executor to keep the event-loop free.
    """

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a PPTX file and return a ParsedDocument.

        Args:
            file_path: Absolute path to the PPTX file.

        Returns:
            ParsedDocument with one ParsedPage per slide.

        Raises:
            FileNotFoundError: If file_path does not exist.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PPTX file not found: {file_path}")

        file_name = Path(file_path).name
        loop = asyncio.get_event_loop()

        pages: List[ParsedPage] = []
        try:
            pages = await loop.run_in_executor(
                None, _parse_with_python_pptx, file_path
            )
            logger.info(
                "Parsed '%s' with python-pptx (%d slides).", file_name, len(pages)
            )
        except Exception as primary_exc:
            logger.warning(
                "python-pptx failed for '%s' (%s); falling back to unstructured.",
                file_name,
                primary_exc,
            )
            try:
                pages = await loop.run_in_executor(None, _parse_with_unstructured, file_path)
                logger.info(
                    "Parsed '%s' with python-pptx (%d slides).", file_name, len(pages)
                )
            except Exception as fallback_exc:
                logger.error(
                    "Both parsers failed for '%s': %s", file_name, fallback_exc
                )
                raise

        # Merge table text into slide text
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
            source="local",
            file_id=file_path,
            access_group="",
            pages=final_pages,
        )
