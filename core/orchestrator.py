# core/orchestrator.py
import asyncio
import copy
import hashlib
import logging
from collections import OrderedDict
from time import perf_counter
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from core.state import PipelineSessionState
from core.mentor_agent import run_socratic_turn

logger = logging.getLogger("orchestrator")

_PIPELINE_CACHE_LIMIT = 8
_pipeline_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()


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
    markdown_result = ""
    started_at = perf_counter()
    try:
        import io
        from ingestion.document_parsers import extract_text
        
        # 1. Заворачиваем байты в поток
        file_stream = io.BytesIO(file_bytes)
        # 2. ВЫЗЫВАЕМ функцию и сохраняем результат!
        markdown_result = await asyncio.to_thread(extract_text, file_stream, file_type)

        logs.append(
            f"✅ [Ingestion Agent] Документ разобран за {perf_counter() - started_at:.1f} с "
            f"({len(markdown_result):,} символов)."
        )
    except Exception as exc:
        # Graceful fallback для изолированной разработки
        logger.warning("Ingestion failed, using fallback: %s", exc)
        if file_bytes:
            try:
                markdown_result = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                markdown_result = "# Извлеченный материал лекции\nКонтент бинарного документа."
        else:
            markdown_result = "# Демонстрационный курс: Алгоритмы и структуры данных\nРазбор обхода графов (DFS)."
        logs.append(f"ℹ️ [Ingestion Agent] Использован базовый парсер текста: {exc}")

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
    started_at = perf_counter()
    try:
        from curriculum.architect_agent import generate_curriculum, prepare_curriculum_source
        prepared_content, was_truncated = prepare_curriculum_source(markdown_content)
        if was_truncated:
            logs.append(
                f"⚡ [Curriculum Architect] Материал сокращён с {len(markdown_content):,} до "
                f"{len(prepared_content):,} символов для быстрого ответа."
            )
        curriculum_data = await asyncio.to_thread(generate_curriculum, prepared_content)
        lesson_plan = curriculum_data.model_dump() if hasattr(curriculum_data, "model_dump") else curriculum_data
        logs.append(f"✅ [Curriculum Architect] План сгенерирован за {perf_counter() - started_at:.1f} с.")
    except Exception as e:
        # Graceful fallback для изолированной разработки
        logger.warning(f"Ошибка архитектора: {e}. Используем фоллбэк.")
        lesson_plan = {
            "title": "Основы графов и поиск в глубину (DFS)",
            "summary": "Разбор рекурсивного обхода графа, структуры стека и отслеживания посещенных вершин.",
            "concepts": ["Граф", "Стек вызовов", "Множество visited", "Рекурсия"],
            "quizzes": [
                {
                    "concept": "Множество visited",
                    "problem_statement": "Реализуйте функцию dfs(graph, start, visited=None), возвращающую порядок обхода вершин."
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

    started_at = perf_counter()
    final_response = ""
    async for event in run_socratic_turn(chat_history, tools_registry, lesson_plan):
        if event["type"] == "thought":
            logs.append(event["content"])
        elif event["type"] == "answer":
            final_response = event["content"]

    chat_history.append({"role": "assistant", "content": final_response})
    logs.append(f"✅ [Socratic Mentor] Ход завершён за {perf_counter() - started_at:.1f} с.")

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
    cache_key = hashlib.sha256(f"{file_type.lower()}\0".encode() + file_bytes).hexdigest()
    cached_result = _pipeline_cache.get(cache_key)
    if cached_result is not None:
        _pipeline_cache.move_to_end(cache_key)
        result = copy.deepcopy(cached_result)
        result["thought_logs"] = ["⚡ [Cache] Для этого файла использован ранее построенный курс."]
        return result

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
    cache_entry = copy.deepcopy(result)
    # The parsed result is useful on a cache hit; retaining every raw PDF is not.
    cache_entry["raw_file_bytes"] = None
    _pipeline_cache[cache_key] = cache_entry
    _pipeline_cache.move_to_end(cache_key)
    while len(_pipeline_cache) > _PIPELINE_CACHE_LIMIT:
        _pipeline_cache.popitem(last=False)
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
