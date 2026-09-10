"""Generate a typed curriculum from unstructured educational material."""

from openai import OpenAI, OpenAIError

from curriculum.schemas import CurriculumSchema


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
        RuntimeError: If the OpenAI request fails, is refused, or is not parsed.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text must contain educational material.")

    try:
        client = OpenAI()
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text.strip()},
            ],
            response_format=CurriculumSchema,
        )

        message = completion.choices[0].message
        if message.refusal:
            raise RuntimeError(f"The model refused the request: {message.refusal}")

        curriculum = message.parsed
        if curriculum is None:
            raise RuntimeError("The model returned no structured curriculum.")

        return curriculum
    except OpenAIError as exc:
        raise RuntimeError("Unable to generate the curriculum through OpenAI.") from exc
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError("OpenAI returned an unexpected curriculum response.") from exc
