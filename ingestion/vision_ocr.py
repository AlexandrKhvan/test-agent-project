"""Vision-assisted extraction of text, diagrams, and mathematical formulas."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import TypeAlias

logger = logging.getLogger(__name__)

ImageSource: TypeAlias = bytes | bytearray | memoryview | str | Path

_OCR_PROMPT = """Extract this educational image into clean Markdown.

Transcribe every visible text element, preserving its reading order and any
apparent headings. Describe diagrams, charts, arrows, labels, relationships,
and annotations clearly enough that a student can understand them without the
image. Transcribe every mathematical formula exactly; format formulas strictly
as LaTeX, using inline `\\(...\\)` or display `\\[...\\]` delimiters. Do not
invent content. Mark genuinely unreadable material as `[illegible]`.
Return only the extracted Markdown, with no preamble."""


def _image_bytes_and_mime(image_path_or_bytes: ImageSource) -> tuple[bytes, str]:
    """Read supported input without exposing filesystem errors to callers."""
    if isinstance(image_path_or_bytes, (bytes, bytearray, memoryview)):
        return bytes(image_path_or_bytes), "image/png"

    image_path = Path(image_path_or_bytes)
    image_bytes = image_path.read_bytes()
    mime_type, _ = mimetypes.guess_type(image_path.name)
    return image_bytes, mime_type or "image/png"


def extract_text_from_image(image_path_or_bytes: ImageSource) -> str:
    """Extract image content through OpenAI Vision, returning "" on failure."""
    try:
        image_bytes, mime_type = _image_bytes_and_mime(image_path_or_bytes)
        if not image_bytes:
            logger.warning("OCR skipped because the image was empty.")
            return ""

        from openai import OpenAI
        import os
        from dotenv import load_dotenv

        # 1. Принудительно читаем файл .env
        load_dotenv()

        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        
        # 2. Подменяем OpenAI на бесплатный Gemini, как просил тимлид
        client = OpenAI(
            api_key=os.environ.get("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        
        # 3. Меняем модель с gpt-4o-mini на gemini-2.0-flash
        response = client.chat.completions.create(
            model="gemini-3.6-flash",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("Vision OCR failed: %s", exc)
        return ""