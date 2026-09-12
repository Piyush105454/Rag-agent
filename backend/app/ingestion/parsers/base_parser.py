"""
base_parser.py — Abstract base class for document parsers.

Defines the ParsedDocument and ParsedPage dataclasses that are the shared
output contract for all parsers (PDF, PPTX, etc.) in the ingestion pipeline.
Any new file-type parser must subclass BaseParser and implement parse().
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List


@dataclass
class ParsedPage:
    """Represents a single page (PDF) or slide (PPTX) of a parsed document.

    Attributes:
        page_number: 0-indexed page/slide number.
        text:        Concatenated plain text extracted from the page.
        tables:      List of tables extracted as plain text (markdown-style).
    """

    page_number: int
    text: str
    tables: List[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """The output of any BaseParser implementation.

    Attributes:
        file_name:    Original filename (e.g. 'Q3_report.pdf').
        source:       Where the file came from: 'drive' | 'local'.
        file_id:      Unique identifier for deduplication (Drive file ID or
                      file path hash).
        access_group: The access-group string controlling who may query this
                      document.
        pages:        Ordered list of ParsedPage objects.
    """

    file_name: str
    source: str
    file_id: str
    access_group: str
    pages: List[ParsedPage]


class BaseParser(abc.ABC):
    """Abstract base class for document parsers.

    Concrete implementations (PDFParser, PPTXParser, ...) must override
    the parse() method and return a ParsedDocument.
    """

    @abc.abstractmethod
    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse *file_path* and return a structured ParsedDocument.

        Args:
            file_path: Absolute path to the file on the local filesystem.

        Returns:
            ParsedDocument containing all extracted pages.

        Raises:
            FileNotFoundError: If file_path does not exist.
            ValueError: If the file is of an unsupported format.
        """
        ...
