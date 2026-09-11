"""Safe converters from supported learning materials to Markdown.

Each public extractor deliberately returns an empty string on a recoverable
error.  This keeps ingestion failures local to the uploaded document instead
of bringing down the application; callers may use logging or an empty-result
message in their own UI.
"""

from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO
import logging
from pathlib import Path
import re
from typing import BinaryIO, Callable, TypeAlias

from ingestion.vision_ocr import extract_text_from_image

logger = logging.getLogger(__name__)

DocumentSource: TypeAlias = bytes | bytearray | memoryview | str | Path | BinaryIO

_BLANK_LINES = re.compile(r"\n{3,}")
_TEX_HEADINGS: tuple[tuple[str, int], ...] = (
    ("chapter", 1),
    ("section", 2),
    ("subsection", 3),
    ("subsubsection", 4),
    ("paragraph", 5),
)


def _read_bytes(source: DocumentSource) -> bytes:
    """Read bytes from an upload, path, or binary file object."""
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()

    data = source.read()
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def _clean_markdown(parts: Iterable[str]) -> str:
    """Remove noisy whitespace while retaining Markdown structure."""
    cleaned = "\n\n".join(part.strip() for part in parts if part and part.strip())
    cleaned = _BLANK_LINES.sub("\n\n", cleaned)
    return cleaned.strip()


def _safe_extract(action: str, extractor: Callable[[], str]) -> str:
    try:
        return extractor()
    except Exception as exc:  # Third-party document libraries can raise varied errors.
        logger.warning("Unable to extract text from %s: %s", action, exc)
        return ""


def extract_pdf_text(source: DocumentSource) -> str:
    """Extract page text from a PDF using :mod:`pypdf` as Markdown."""
    def extract() -> str:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(_read_bytes(source)))
        pages = (page.extract_text() or "" for page in reader.pages)
        return _clean_markdown(pages)

    return _safe_extract("PDF", extract)


def extract_docx_text(source: DocumentSource) -> str:
    """Extract paragraphs and heading styles from a DOCX document."""
    def extract() -> str:
        from docx import Document

        document = Document(BytesIO(_read_bytes(source)))
        parts: list[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style_name = (paragraph.style.name or "").lower()
            match = re.search(r"heading\s*([1-6])", style_name)
            if match:
                parts.append(f"{'#' * int(match.group(1))} {text}")
            elif style_name == "title":
                parts.append(f"# {text}")
            else:
                parts.append(text)
        return _clean_markdown(parts)

    return _safe_extract("DOCX", extract)


def extract_pptx_text(source: DocumentSource) -> str:
    """Extract slide titles and visible text from a PPTX presentation."""
    def extract() -> str:
        from pptx import Presentation

        presentation = Presentation(BytesIO(_read_bytes(source)))
        slides: list[str] = []
        for number, slide in enumerate(presentation.slides, start=1):
            title_shape = slide.shapes.title
            title = title_shape.text.strip() if title_shape is not None else ""
            body: list[str] = []
            for shape in slide.shapes:
                if not getattr(shape, "has_text_frame", False) or shape == title_shape:
                    continue
                text = shape.text.strip()
                if text:
                    body.append(text)
            heading = f"## {title}" if title else f"## Slide {number}"
            slides.append(_clean_markdown([heading, *body]))
        return _clean_markdown(slides)

    return _safe_extract("PPTX", extract)


def extract_plain_text(source: DocumentSource) -> str:
    """Decode Markdown, TeX, or ordinary text without losing existing headings."""
    def extract() -> str:
        raw = _read_bytes(source)
        text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
        return _clean_markdown([_tex_to_markdown_headings(text)])

    return _safe_extract("plain-text document", extract)


def _tex_to_markdown_headings(text: str) -> str:
    """Map common LaTeX section commands to Markdown headings."""
    for command, level in _TEX_HEADINGS:
        pattern = r"(?m)^\s\\" + command + r"\*?\{([^}]+)\}\s*$"
        text = re.sub(pattern, lambda match: f"{'#' * level} {match.group(1).strip()}", text)
    return text


def extract_text(source: DocumentSource, file_type: str) -> str:
    """Dispatch extraction by extension or MIME-like ``file_type`` string.

    Unknown types and all parser failures return an empty string.
    """
    normalized = file_type.lower().strip().lstrip(".")
    if normalized in {"pdf", "application/pdf"}:
        return extract_pdf_text(source)
    if normalized in {"docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
        return extract_docx_text(source)
    if normalized in {"pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"}:
        return extract_pptx_text(source)
    if normalized in {"tex", "latex", "md", "markdown", "txt", "text/plain"}:
        return extract_plain_text(source)
    if normalized in {"png", "jpg", "jpeg", "image/png", "image/jpeg"}:
        return extract_text_from_image(source)
    logger.warning("Unsupported document type: %s", file_type)
    return ""


# Short aliases support straightforward use from a parser router.
parse_pdf = extract_pdf_text
parse_docx = extract_docx_text
parse_pptx = extract_pptx_text
parse_text = extract_plain_text
