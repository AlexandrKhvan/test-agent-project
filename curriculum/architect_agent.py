"""Generate a typed curriculum from unstructured educational material."""

import os
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from curriculum.schemas import CurriculumSchema

load_dotenv()

SYSTEM_PROMPT = """
You are an expert educational architect who turns source material into a focused,
practical learning experience. Analyse only the supplied material and preserve its
language. Create a concise, accurate course title and extract the concepts that a
learner must understand to use the material in practice.

For the quiz, write practical, scenario-based multiple-choice questions that test
understanding rather than rote recall. Each question must have clear options, one
unambiguously correct answer, and `correct_answer` must exactly match one string
in `options`. Do not invent facts that are unsupported by the source material.
""".strip()


def generate_curriculum(raw_text: str) -> CurriculumSchema:
    """Build a structured curriculum from extracted document text.

    Raises:
        ValueError: If ``raw_text`` is empty.
        RuntimeError: If the request fails, is refused, or is not parsed.
    """
    if not raw_text or not raw_text.strip():
        return CurriculumSchema(title="", key_concepts=[], quiz=[])
    try:
        # 1. Читаем .env файл (где лежит GEMINI_API_KEY)
        load_dotenv()
        
        # 2. Подменяем OpenAI на Gemini через совместимый API
        client = OpenAI(
            api_key=os.environ.get("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        
        # 3. Используем модель Gemini с поддержкой Structured Outputs
        completion = client.beta.chat.completions.parse(
            model="gemini-3.6-flash",
            model="gemini-3.6-flash",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text.strip()},
            ],
            response_format=CurriculumSchema,
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