# core/mentor_agent.py
import json
import asyncio
import inspect
import os
import re
from time import perf_counter
from typing import AsyncGenerator, Dict, Any, List
from core.llm_client import get_async_llm_client

SOCRATIC_SYSTEM_PROMPT = """
Ты — элитный преподаватель Computer Science и алгоритмов, обучающий строго по методу Сократа.

ТВОИ ПРАВИЛА:
1. НИКОГДА не давай готовое решение или законченный кусок кода студенту.
2. Отвечай наводящими вопросами, разбивай задачу на мелкие шаги, заставляй студента думать.
3. Если студент прислал код на проверку — ОБЯЗАТЕЛЬНО вызови инструмент `run_code_sandbox`.
4. Если код упал с ошибкой — укажи студенту на тип ошибки и спроси, в какой строке или логике кроется причина, не исправляя её самостоятельно.
5. Опирайся на материалы сформированного урока (Lesson Plan).
"""

# JSON Schema инструмента песочницы для Function Calling
SANDBOX_TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_code_sandbox",
            "description": "Запускает код на Python в изолированной среде и возвращает stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Исходный Python код для тестирования"
                    }
                },
                "required": ["code"]
            }
        }
    }
]

_CODE_HINT = re.compile(
    r"```(?:python)?|^\s*(?:def |class |for |while |if |print\(|[A-Za-z_]\w*\s*=)",
    re.IGNORECASE | re.MULTILINE,
)


def _positive_int(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default)).replace("_", "")))
    except ValueError:
        return default


def _limit_text(value: Any, maximum: int) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) <= maximum:
        return text
    return f"{text[:maximum]}\n[...сокращено для быстрого контекста...]"


def _compact_history(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use recent dialogue turns; old turns are the main source of chat latency."""
    max_messages = _positive_int("MENTOR_HISTORY_MESSAGES", 8, 2)
    max_message_chars = _positive_int("MENTOR_MESSAGE_MAX_CHARS", 8_000, 1_000)
    compacted: List[Dict[str, Any]] = []
    for message in messages[-max_messages:]:
        role = message.get("role", "user")
        content = _limit_text(message.get("content", ""), max_message_chars)
        compacted.append({"role": role, "content": content})
    return compacted


def _compact_lesson_plan(lesson_plan: Dict[str, Any]) -> str:
    """Keep the lesson relevant without resending an arbitrarily large quiz."""
    maximum = _positive_int("MENTOR_LESSON_PLAN_MAX_CHARS", 6_000, 1_000)
    return _limit_text(json.dumps(lesson_plan, ensure_ascii=False), maximum)


async def run_socratic_turn(
    messages: List[Dict[str, Any]],
    available_tools: Dict[str, Any],
    lesson_plan: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Выполняет один интерактивный ход ментора со стримингом мыслей и ответов.
    """
    client, model_name = get_async_llm_client()
    
    # Формируем контекст с системным промптом и конспектом урока
    context_messages: List[Dict[str, Any]] = []
    system_text = SOCRATIC_SYSTEM_PROMPT
    if lesson_plan:
        system_text += f"\n\nТЕКУЩИЙ УРОК:\nЗадачи и концепты: {_compact_lesson_plan(lesson_plan)}"

    context_messages.append({"role": "system", "content": system_text})
    recent_messages = _compact_history(messages)
    context_messages.extend(recent_messages)
    latest_user_message = next(
        (message["content"] for message in reversed(recent_messages) if message["role"] == "user"),
        "",
    )
    code_was_submitted = bool(_CODE_HINT.search(latest_user_message))

    # At most one sandbox round: model -> sandbox -> concise final guidance.
    for step in range(2):
        request_started = perf_counter()
        response = await client.chat.completions.create(
            model=model_name,
            messages=context_messages,
            tools=SANDBOX_TOOL_SCHEMA if code_was_submitted and step == 0 else None,
            tool_choice="auto" if code_was_submitted and step == 0 else None,
            max_tokens=_positive_int("MENTOR_MAX_OUTPUT_TOKENS", 900, 100),
            reasoning_effort=os.getenv("GEMINI_REASONING_EFFORT", "low"),
        )
        finish_reason = response.choices[0].finish_reason or "unknown"
        yield {
            "type": "thought",
            "content": (
                f"⏱️ Ответ модели получен за {perf_counter() - request_started:.1f} с "
                f"(причина завершения: {finish_reason})."
            ),
        }
        
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            context_messages.append(msg)
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}
                
                yield {"type": "thought", "content": f"⚙️ Ментор тестирует код через `{fn_name}`..."}
                
                tool_func = available_tools.get(fn_name)
                if tool_func:
                    try:
                        tool_started = perf_counter()
                        if not callable(tool_func):
                            result = "Tool not callable"
                        elif inspect.iscoroutinefunction(tool_func):
                            result = await tool_func(**fn_args)
                        else:
                            result = await asyncio.to_thread(tool_func, **fn_args)
                        yield {"type": "thought", "content": f"⏱️ Песочница завершилась за {perf_counter() - tool_started:.1f} с."}
                    except Exception as e:
                        result = {"success": False, "error": str(e)}
                else:
                    result = {"error": f"Инструмент {fn_name} не зарегистрирован"}

                context_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": json.dumps(result, ensure_ascii=False)
                })
        else:
            # Ответ готов
            yield {"type": "answer", "content": msg.content or "Опиши, пожалуйста, свой следующий шаг — я помогу его проверить."}
            break
    else:
        yield {"type": "answer", "content": "Песочница завершила проверку. Какой результат или строка кода кажется тебе сомнительной?"}
