"""Routing layer for turning supported uploads into normalized Markdown."""

from __future__ import annotations

import logging
import os
from typing import Any

from ingestion.document_parsers import extract_text
from ingestion.vision_ocr import extract_text_from_image

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".docx", ".md", ".pptx", ".tex", ".txt"})


def _result(
    *,
    filename: str,
    file_type: str,
    content: str = "",
    success: bool,
    error: str | None = None,
) -> dict[str, Any]:
    """Return the stable ingestion-result schema used by pipeline callers."""
    return {
        "filename": filename,
        "file_type": file_type,
        "content": content,
        "success": success,
        "error": error,
    }


class ParserAgent:
    """Select a document or vision parser based on the uploaded filename."""

    def parse_file(self, file_path: str) -> dict[str, Any]:
        """Parse one local file without allowing a parser failure to propagate."""
        filename = os.path.basename(file_path)
        file_type = os.path.splitext(filename)[1].lower()

        if not os.path.exists(file_path):
            return _result(
                filename=filename,
                file_type=file_type,
                success=False,
                error=f"File not found: {file_path}",
            )

        try:
            if file_type in _IMAGE_EXTENSIONS:
                content = extract_text_from_image(file_path)
                empty_error = "Vision OCR returned empty text."
            elif file_type in _DOCUMENT_EXTENSIONS:
                content = extract_text(file_path, file_type)
                empty_error = "Document parser returned empty text."
            else:
                return _result(
                    filename=filename,
                    file_type=file_type,
                    success=False,
                    error=f"Unsupported file extension: {file_type}",
                )
        except Exception as exc:
            logger.exception("Failed to parse '%s'", file_path)
            return _result(
                filename=filename,
                file_type=file_type,
                success=False,
                error=f"Parser error: {exc}",
            )

        if content is None or not isinstance(content, str) or not content.strip():
            return _result(
                filename=filename,
                file_type=file_type,
                success=False,
                error=empty_error,
            )

        return _result(filename=filename, file_type=file_type, content=content, success=True)


def run_ingestion(file_path: str) -> dict[str, Any]:
    """Public entry point used by the orchestration layer."""
    return ParserAgent().parse_file(file_path)