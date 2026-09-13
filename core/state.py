# core/state.py
from typing import TypedDict, Optional, List, Dict, Any

class PipelineSessionState(TypedDict):
    """
    Глобальное состояние образовательного пайплайна.
    Передается сквозь узлы Ingestion -> Curriculum Architect -> Socratic Mentor.
    """
    # Входные сырые данные от пользователя
    raw_file_bytes: Optional[bytes]
    file_type: str
    filename: str

    # Данные после Агента 1 (Ingestion)
    parsed_markdown: str
    material_index: List[Dict[str, Any]]
    curriculum_source: str

    # Данные после Агента 2 (Curriculum Architect)
    lesson_plan: Optional[Dict[str, Any]]

    # Диалог со студентом (Агент 3: Mentor)
    chat_history: List[Dict[str, Any]]
    student_latest_input: str
    mentor_response: str
    
    # Трейсы рассуждений и работы тулов для UI (st.status)
    thought_logs: List[str]
