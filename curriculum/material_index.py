"""Local, section-aware indexing for large learning materials.

The index intentionally uses no embedding API: it keeps the free-tier pipeline
fast and lets the mentor retrieve the original text that matches a question.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_HEADING_PATTERN = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
_WORD_PATTERN = re.compile(r"[\w-]{3,}", re.UNICODE)
_DEFAULT_CHUNK_CHARS = 8_000
_DEFAULT_CHUNK_OVERLAP_CHARS = 400


def _words(text: str) -> set[str]:
    return {word.lower() for word in _WORD_PATTERN.findall(text)}


def _heading_for(text: str, fallback: str) -> str:
    match = _HEADING_PATTERN.search(text)
    return match.group(2).strip() if match else fallback


def split_material_into_chunks(
    markdown: str,
    *,
    chunk_size: int = _DEFAULT_CHUNK_CHARS,
    overlap: int = _DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[dict[str, str]]:
    """Split Markdown at headings first, then safely split oversized sections."""
    cleaned = markdown.strip()
    if not cleaned:
        return []

    sections: list[str] = []
    starts = [match.start() for match in _HEADING_PATTERN.finditer(cleaned)]
    if starts and starts[0] > 0:
        starts.insert(0, 0)
    if not starts:
        starts = [0]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(cleaned)
        section = cleaned[start:end].strip()
        if section:
            sections.append(section)

    chunks: list[dict[str, str]] = []
    buffer = ""
    for section in sections:
        if buffer and len(buffer) + len(section) + 2 > chunk_size:
            chunks.append({"title": _heading_for(buffer, f"Раздел {len(chunks) + 1}"), "content": buffer})
            buffer = ""
        if len(section) <= chunk_size:
            buffer = f"{buffer}\n\n{section}".strip()
            continue

        if buffer:
            chunks.append({"title": _heading_for(buffer, f"Раздел {len(chunks) + 1}"), "content": buffer})
            buffer = ""
        start = 0
        while start < len(section):
            end = min(len(section), start + chunk_size)
            if end < len(section):
                boundary = section.rfind("\n", start, end)
                if boundary > start + chunk_size // 2:
                    end = boundary
            content = section[start:end].strip()
            if content:
                chunks.append({"title": _heading_for(content, f"Раздел {len(chunks) + 1}"), "content": content})
            if end >= len(section):
                break
            start = max(end - overlap, start + 1)

    if buffer:
        chunks.append({"title": _heading_for(buffer, f"Раздел {len(chunks) + 1}"), "content": buffer})

    return [
        {"id": f"section-{index}", "title": chunk["title"], "content": chunk["content"]}
        for index, chunk in enumerate(chunks, start=1)
    ]


def build_course_digest(chunks: list[dict[str, str]], max_chars: int) -> str:
    """Represent every section in a bounded global-course prompt.

    Each chunk gets a fair budget, so a late lecture cannot disappear merely
    because an early lecture was long. The original chunk remains available for
    retrieval during mentoring.
    """
    if not chunks:
        return ""
    separator_size = 2 * (len(chunks) - 1)
    per_chunk = max(64, (max_chars - separator_size) // len(chunks))
    previews: list[str] = []
    for chunk in chunks:
        content = re.sub(r"\s+", " ", chunk["content"]).strip()
        title_limit = max(24, per_chunk // 3)
        title = chunk["title"][:title_limit]
        excerpt_limit = max(0, per_chunk - len(title) - 4)
        excerpt = content[:excerpt_limit].rsplit(" ", 1)[0] or content[:excerpt_limit]
        previews.append(f"## {title}\n{excerpt}")
    return "\n\n".join(previews)


def retrieve_relevant_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    *,
    limit: int = 3,
    max_chunk_chars: int = 4_000,
) -> list[dict[str, str]]:
    """Return the best local lexical matches, with deterministic fallbacks."""
    query_words = _words(question)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for position, chunk in enumerate(chunks):
        title = str(chunk.get("title", ""))
        content = str(chunk.get("content", ""))
        title_words = _words(title)
        content_counts = Counter(_WORD_PATTERN.findall(content.lower()))
        score = sum(3 for word in query_words if word in title_words)
        score += sum(min(2, content_counts[word]) for word in query_words)
        scored.append((score, -position, chunk))

    selected = sorted(scored, reverse=True)[:limit]
    results: list[dict[str, str]] = []
    for _, _, chunk in selected:
        content = str(chunk.get("content", ""))
        results.append(
            {
                "id": str(chunk.get("id", "")),
                "title": str(chunk.get("title", "Раздел материала")),
                "content": content[:max_chunk_chars],
            }
        )
    return results
