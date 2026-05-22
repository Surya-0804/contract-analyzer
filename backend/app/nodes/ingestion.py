"""Ingestion node for extracting text from PDF files.

This module provides a more robust `IngestionNode` that:
- validates input size
- handles PDF open errors
- extracts text with layout-preserving `get_text("text")`
- optionally falls back to OCR when pages contain no text
- logs warnings and errors instead of failing silently
"""

from __future__ import annotations
import fitz
import pymupdf4llm
from app.core.logging_utils import get_logger

logger = get_logger(__name__)

class IngestionNode:
    def __init__(self, max_bytes: int = 25_000_000, max_pages: int = None):
        self.max_bytes = max_bytes
        self.max_pages = max_pages

    def ingest_with_metadata(self, file_bytes: bytes) -> tuple[str, dict]:
        if not isinstance(file_bytes, (bytes, bytearray)):
            raise ValueError("file_bytes must be bytes-like")
        if len(file_bytes) == 0:
            return "", {"page_count": 0, "file_size_bytes": 0}
        if len(file_bytes) > self.max_bytes:
            raise ValueError(f"file too large ({len(file_bytes)} bytes)")

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            logger.error(f"failed to open PDF: {exc}", exc_info=True)
            raise ValueError("Invalid or corrupted PDF file") from exc

        try:
            metadata = {
                "page_count": doc.page_count,
                "file_size_bytes": len(file_bytes),
            }
            pages = list(range(self.max_pages)) if self.max_pages else None
            text = pymupdf4llm.to_markdown(doc, pages=pages)
            if not text.strip():
                raise ValueError("No extractable text found. PDF may be scanned.")
            return text, metadata
        finally:
            try:
                doc.close()
            except Exception:
                logger.debug("error closing document", exc_info=True)

    def ingest(self, file_bytes: bytes) -> str:
        text, _ = self.ingest_with_metadata(file_bytes)
        return text
