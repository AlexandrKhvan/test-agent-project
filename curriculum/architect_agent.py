"""Generate a typed curriculum from unstructured educational material."""

import os
import re
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from curriculum.schemas import CurriculumSchema

load_dotenv()

SYSTEM_PROMPT = """
You are an expert educational architect who turns source material into a focused,
practical learning experience. Analyse only the supplied material and preserve its
language. Create a concise, accurate course title and extract the concepts that a
learner must understand to use the material in practice.

Return at most four key concepts and exactly two concise, practical
multiple-choice questions. Each question must have exactly three short options,
one unambiguously correct answer, and `correct_answer` must exactly match one
string in `options`. Do not invent facts that are unsupported by the source
material.
""".strip()

_DEFAULT_MAX_SOURCE_CHARS = 24_000
_DEFAULT_MAX_OUTPUT_TOKENS = 1_800


def _environment_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).replace("_", ""))
    except ValueError:
        return default


def _environment_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_curriculum_source_limit() -> int:
    """Return the shared source budget for both direct and indexed materials."""
    return max(4_000, _environment_int("CURRICULUM_MAX_SOURCE_CHARS", _DEFAULT_MAX_SOURCE_CHARS))


def prepare_curriculum_source(raw_text: str) -> tuple[str, bool]:
    """Keep a long upload within a predictable free-tier prompt budget.

    The opening normally contains the topic and definitions, while the ending
    often contains conclusions or exercises.  Retaining both is more useful
    than silently discarding the tail of a lecture.
    """
    normalized = re.sub(r"\n{3,}", "\n\n", raw_text).strip()
    max_chars = get_curriculum_source_limit()

    if len(normalized) <= max_chars:
        return normalized, False

    head_size = int(max_chars * 0.8)
    tail_size = max_chars - head_size
    truncated = (
        f"{normalized[:head_size]}\n\n"
        "[Материал сокращён для быстрого построения курса; далее — завершающий фрагмент.]\n\n"
        f"{normalized[-tail_size:]}"
    )
    return truncated, True


def generate_curriculum(raw_text: str) -> CurriculumSchema:
    """Build a structured curriculum from extracted document text.

    Raises:
        ValueError: If ``raw_text`` is empty.
        RuntimeError: If the request fails, is refused, or is not parsed.
    """
    if not raw_text or not raw_text.strip():
        return CurriculumSchema(title="", key_concepts=[], quiz=[])
    source_text, _ = prepare_curriculum_source(raw_text)
    try:
        # 1. Читаем .env файл (где лежит GEMINI_API_KEY)
        load_dotenv()
        
        # 2. Подменяем OpenAI на Gemini через совместимый API
        client = OpenAI(
            api_key=os.environ.get("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=max(5.0, _environment_float("LLM_TIMEOUT_SECONDS", 35.0)),
            max_retries=max(0, _environment_int("LLM_MAX_RETRIES", 1)),
        )
        
        # 3. Используем модель Gemini с поддержкой Structured Outputs
        completion = client.beta.chat.completions.parse(
            model="gemini-3.6-flash",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": source_text},
            ],
            response_format=CurriculumSchema,
            max_tokens=max(100, _environment_int("CURRICULUM_MAX_OUTPUT_TOKENS", _DEFAULT_MAX_OUTPUT_TOKENS)),
            reasoning_effort=os.getenv("GEMINI_REASONING_EFFORT", "low"),
        )

        message = completion.choices[0].message
        
        # Безопасная проверка на отказ модели
        if getattr(message, "refusal", None):
            raise RuntimeError(f"The model refused the request: {message.refusal}")

        curriculum = message.parsed
        if curriculum is None:
            return CurriculumSchema(title="", key_concepts=[], quiz=[])

        return curriculum
    except OpenAIError as exc:
        # Измененный текст ошибки, чтобы мы сразу видели причину
        raise RuntimeError(f"Unable to generate the curriculum: {exc}") from exc
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError("API returned an unexpected curriculum response.") from exc
