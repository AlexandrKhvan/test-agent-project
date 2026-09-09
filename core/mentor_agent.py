# core/mentor_agent.py
import json
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
    context_messages = []
    system_text = SOCRATIC_SYSTEM_PROMPT
    if lesson_plan:
        system_text += f"\n\nТЕКУЩИЙ УРОК:\nЗадачи и концепты: {json.dumps(lesson_plan, ensure_ascii=False)}"
        
    context_messages.append({"role": "system", "content": system_text})
    context_messages.extend(messages)

    # ReAct цикл: максимум 5 шагов на вызовы инструментов
    for step in range(5):
        response = await client.chat.completions.create(
            model=model_name,
            messages=context_messages,
            tools=SANDBOX_TOOL_SCHEMA,
            tool_choice="auto"
        )
        
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            context_messages.append(msg)
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                
                yield {"type": "thought", "content": f"⚙️ Ментор тестирует код через `{fn_name}`..."}
                
                tool_func = available_tools.get(fn_name)
                if tool_func:
                    try:
                        result = await tool_func(**fn_args) if callable(tool_func) else "Tool not callable"
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
            yield {"type": "answer", "content": msg.content}
            break