# ОБЩИЙ СИСТЕМНЫЙ КОНТЕКСТ ПРОЕКТА: Socratic AI Pipeline (HackAlem AI 2026)

## 1. КОНЦЕПЦИЯ И АРХИТЕКТУРА
Мы разрабатываем 3-агентный образовательный конвейер "Socratic AI Tutor":
1. Агент 1 (Ingestion Agent): Принимает любые учебные материалы (PDF, DOCX, PPTX, LaTeX, MD, изображения схем) и нормализует их в структурированный Markdown.
2. Агент 2 (Curriculum Architect): Анализирует Markdown, извлекает граф ключевых концепций, строит краткий конспект (cheat-sheet) и генерирует проверочные задачи с тестовыми кейсами в формате Pydantic/JSON.
3. Агент 3 (Socratic Mentor): Интерактивный ReAct-агент. Опираясь на данные от Агента 2, ведет сократический диалог (НЕ выдает готовые решения, задает наводящие вопросы) и запускает код студента в изолированной песочнице.

## 2. СТЕК ТЕХНОЛОГИЙ
- Python 3.11+, пакетный менеджер uv.
- OpenAI API (gpt-4o-mini для парсинга/структурирования, gpt-4o для ментора).
- Оркестрация: LangGraph (StateGraph), OpenAI Structured Outputs (Pydantic v2).
- Бэкенд и интерфейс: FastAPI (SSE streaming), Streamlit.
- Парсинг: pypdf, python-docx, python-pptx, markdown, OpenAI Vision API.

## 3. СТРОГИЕ ПРАВИЛА КОДА
- Строгая типизация везде (type hints).
- Все ошибки инструментов (Tool errors / execution failures) перехватываются через try/except и возвращаются агенту в виде JSON (Self-correction), не краша приложение.
- Четкое разделение по папкам: core/, ingestion/, curriculum/, app/, ui/.