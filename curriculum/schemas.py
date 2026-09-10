"""Structured data models for an educational curriculum."""

from pydantic import BaseModel


class QuizItem(BaseModel):
    """A single multiple-choice question generated from the study material."""

    question: str
    options: list[str]
    correct_answer: str


class CurriculumSchema(BaseModel):
    """The course plan returned by the curriculum architect."""

    title: str
    key_concepts: list[str]
    quiz: list[QuizItem]
