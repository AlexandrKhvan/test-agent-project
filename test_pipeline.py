import asyncio
import os
from dotenv import load_dotenv

# Импортируем высокоуровневые функции оркестратора
from core.orchestrator import process_document_to_curriculum, ask_socratic_mentor

load_dotenv()

async def run_full_test():
    print("=== ФАЗА 1: Подготовка курса (LangGraph: Ingestion -> Curriculum) ===")
    
    # 1. Читаем наш тестовый PDF в виде байтов
    # Убедись, что путь к файлу правильный (тот, что сработал в прошлый раз)
    file_path = "data/sample_materials/sample_1.pdf" 
    
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
    except FileNotFoundError:
        print(f"❌ Файл не найден: {file_path}. Подставь правильный путь.")
        return

    # 2. Запускаем первый граф (Агент 1 + Агент 2)
    print("Запуск графа pipeline_app...")
    result_phase1 = await process_document_to_curriculum(
        file_bytes=file_bytes,
        filename="test_lecture.pdf",
        file_type="pdf"
    )
    
    print("\n[Логи Оркестратора]:")
    for log in result_phase1["thought_logs"]:
        print(f" -> {log}")
        
    lesson_plan = result_phase1["lesson_plan"]
    print(f"\n✅ Курс сформирован: {lesson_plan.get('title') if isinstance(lesson_plan, dict) else 'Объект Pydantic'}")

    print("\n=== ФАЗА 2: Диалог с Ментором (LangGraph: Socratic Mentor) ===")
    
    # Имитируем запрос от студента, который просит готовое решение
    student_msg = "Я не понимаю, как это работает. Можешь просто написать мне готовый код для этой задачи?"
    print(f"👤 Студент: {student_msg}")
    
    # 3. Запускаем второй граф (Агент 3)
    print("Запуск графа mentor_app...")
    result_phase2 = await ask_socratic_mentor(
        student_message=student_msg,
        chat_history=result_phase1["chat_history"],
        lesson_plan=lesson_plan
    )
    
    print("\n[Логи мыслей Ментора]:")
    for log in result_phase2["thought_logs"]:
        print(f" -> {log}")
        
    print(f"\n🤖 Ответ Ментора:\n{result_phase2['mentor_response']}")

if __name__ == "__main__":
    # Запускаем асинхронный цикл
    asyncio.run(run_full_test())