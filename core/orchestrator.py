# core/orchestrator.py
import json
import logging
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from core.state import PipelineSessionState
from core.mentor_agent import run_socratic_turn

logger = logging.getLogger("orchestrator")


# =====================================================================
# 1. Определение узлов графа (Pipeline Nodes)
# =====================================================================

async def ingestion_node(state: PipelineSessionState) -> Dict[str, Any]:
    """
    Узел 1: Агент парсинга материалов (Ingestion Agent).
    Принимает байты файла, определяет тип и нормализует в единый Markdown.
    """
    file_bytes = state.get("raw_file_bytes")
    filename = state.get("filename", "unknown.txt")
    file_type = state.get("file_type", "txt")
    
    logs = list(state.get("thought_logs", []))
    logs.append(f"📄 [Ingestion Agent] Обработка файла `{filename}` ({file_type})...")

    # Пытаемся вызвать реализацию Напарника 1, если модуль уже слит
    try:
        from ingestion.parser_agent import parse_document
        markdown_result = await parse_document(file_bytes=file_bytes, filename=filename)
        logs.append("✅ [Ingestion Agent] Документ успешно разобран и структурирован в Markdown.")
    except (ImportError, AttributeError):
        # Graceful fallback для изолированной разработки
        logger.warning("ingestion.parser_agent еще не реализован. Используем фоллбэк.")
        if file_bytes:
            try:
                markdown_result = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                markdown_result = "# Извлеченный материал лекции\nКонтент бинарного документа."
        else:
            markdown_result = "# Демонстрационный курс: Алгоритмы и структуры данных\nРазбор обхода графов (DFS)."
        logs.append("ℹ️ [Ingestion Agent] Использован базовый парсер текста.")

    return {
        "parsed_markdown": markdown_result,
        "thought_logs": logs
    }


async def curriculum_node(state: PipelineSessionState) -> Dict[str, Any]:
    """
    Узел 2: Архитектор программы обучения (Curriculum Architect).
    Генерирует конспект, граф понятий и практические задания.
    """
    markdown_content = state.get("parsed_markdown", "")
    logs = list(state.get("thought_logs", []))
    logs.append("🧠 [Curriculum Architect] Извлечение ключевых концепций и генерация задач...")

    # Пытаемся вызвать реализацию Напарника 1
    try:
        from curriculum.architect_agent import build_curriculum
        curriculum_data = await build_curriculum(markdown_content)
        lesson_plan = curriculum_data.model_dump() if hasattr(curriculum_data, "model_dump") else curriculum_data
        logs.append("✅ [Curriculum Architect] Учебный план и проверочные кейсы сгенерированы.")
    except (ImportError, AttributeError):
        # Graceful fallback для изолированной разработки
        logger.warning("curriculum.architect_agent еще не реализован. Используем фоллбэк.")
        lesson_plan = {
            "title": "Основы графов и поиск в глубину (DFS)",
            "summary": "Разбор рекурсивного обхода графа, структуры стека и отслеживания посещенных вершин.",
            "concepts": ["Граф", "Стек вызовов", "Множество visited", "Рекурсия"],
            "quizzes": [
                {
                    "concept": "Множество visited",
                    "problem_statement": "Реализуйте функцию dfs(graph, start, visited=None), возвращающую порядок обхода вершин.",
                    "hints": [
                        "Что произойдет, если в графе есть цикл, а visited отсутствует?",
                        "Какую коллекцию в Python эффективнее использовать для быстрой проверки `in` за O(1)?"
                    ]
                }
            ]
        }
        logs.append("ℹ️ [Curriculum Architect] Применен тестовый шаблон учебного плана.")

    return {
        "lesson_plan": lesson_plan,
        "thought_logs": logs
    }


async def mentor_node(state: PipelineSessionState) -> Dict[str, Any]:
    """
    Узел 3: Интерактивный Сократический ментор.
    Реагирует на ввод студента, выполняет ReAct-цикл и отвечает без прямых решений.
    """
    student_input = state.get("student_latest_input", "")
    chat_history = list(state.get("chat_history", []))
    lesson_plan = state.get("lesson_plan")
    logs = list(state.get("thought_logs", []))

    if student_input:
        chat_history.append({"role": "user", "content": student_input})

    logs.append("🎓 [Socratic Mentor] Анализ ответа студента и формулирование наводящего вопроса...")

    # Доступные инструменты (песочница)
    tools_registry = {}
    try:
        from curriculum.sandbox import execute_code
        tools_registry["run_code_sandbox"] = execute_code
    except (ImportError, AttributeError):
        async def mock_sandbox(code: str) -> dict:
            return {"success": True, "stdout": "Mock output: Code executed successfully.", "stderr": ""}
        tools_registry["run_code_sandbox"] = mock_sandbox

    final_response = ""
    async for event in run_socratic_turn(chat_history, tools_registry, lesson_plan):
        if event["type"] == "thought":
            logs.append(event["content"])
        elif event["type"] == "answer":
            final_response = event["content"]

    chat_history.append({"role": "assistant", "content": final_response})

    return {
        "chat_history": chat_history,
        "mentor_response": final_response,
        "thought_logs": logs
    }


# =====================================================================
# 2. Сборка графов LangGraph (Workflows)
# =====================================================================

def build_ingestion_curriculum_pipeline():
    """
    Пайплайн подготовки материалов:
    Документ -> [Ingestion Agent] -> [Curriculum Architect] -> Финал.
    """
    builder = StateGraph(PipelineSessionState)

    builder.add_node("ingestion_agent", ingestion_node)
    builder.add_node("curriculum_architect", curriculum_node)

    builder.set_entry_point("ingestion_agent")
    builder.add_edge("ingestion_agent", "curriculum_architect")
    builder.add_edge("curriculum_architect", END)

    return builder.compile()


def build_mentor_pipeline():
    """
    Интерактивный контур диалога со студентом.
    """
    builder = StateGraph(PipelineSessionState)

    builder.add_node("socratic_mentor", mentor_node)
    builder.set_entry_point("socratic_mentor")
    builder.add_edge("socratic_mentor", END)

    return builder.compile()


# Инициализируем исполняемые приложения графа
pipeline_app = build_ingestion_curriculum_pipeline()
mentor_app = build_mentor_pipeline()


# =====================================================================
# 3. Высокоуровневые фасады для FastAPI и UI
# =====================================================================

async def process_document_to_curriculum(
    file_bytes: bytes,
    filename: str,
    file_type: str
) -> Dict[str, Any]:
    """
    Запускает фазу 1 и 2: преобразование сырого файла в готовый курс.
    """
    initial_state: PipelineSessionState = {
        "raw_file_bytes": file_bytes,
        "filename": filename,
        "file_type": file_type,
        "parsed_markdown": "",
        "lesson_plan": None,
        "chat_history": [],
        "student_latest_input": "",
        "mentor_response": "",
        "thought_logs": []
    }

    result = await pipeline_app.ainvoke(initial_state)
    return result


async def ask_socratic_mentor(
    student_message: str,
    chat_history: list,
    lesson_plan: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Запускает фазу 3: обработку ответа/вопроса студента через ментора.
    """
    initial_state: PipelineSessionState = {
        "raw_file_bytes": None,
        "filename": "",
        "file_type": "",
        "parsed_markdown": "",
        "lesson_plan": lesson_plan,
        "chat_history": chat_history,
        "student_latest_input": student_message,
        "mentor_response": "",
        "thought_logs": []
    }

    result = await mentor_app.ainvoke(initial_state)
    return result
