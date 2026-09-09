# 🎓 Socratic AI Tutor — Autonomous Multi-Agent Educational Pipeline

---

## 1. Концепция и Проблема

Большинство современных AI-ассистентов работают как «генераторы готовых ответов», стимулируя списывание и снижая уровень самостоятельного мышления студентов. 

**Socratic AI Tutor** решает эту проблему через 3-звенный автономный конвейер агентов:
1. **Агент 1 (Ingestion):** Поглощает и оцифровывает учебные материалы любого формата (лекции, презентации, рукописные заметки, сканы задач).
2. **Агент 2 (Curriculum Architect):** Структурирует знания, выделяет ключевые концепции и формулирует практические интерактивные задачи.
3. **Агент 3 (Socratic Mentor):** Интерактивно обучает студента по методу Сократа, запуская код в песочнице и направляя к решению наводящими вопросами без прямых подсказок.

---

## 2. Архитектура Системы

```
[Пользовательский файл: PDF / DOCX / PPTX / TeX / Скан]
                         │
                         ▼
        ┌───────────────────────────────────┐
        │     Агент 1: Ingestion & OCR      │
        │      (ingestion/parser_agent)     │
        └────────────────┬──────────────────┘
                         │  Unified Markdown + LaTeX
                         ▼
        ┌───────────────────────────────────┐
        │  Агент 2: Curriculum Architect    │
        │     (curriculum/architect_agent)  │
        └────────────────┬──────────────────┘
                         │  Structured Pydantic Curriculum
                         ▼
        ┌───────────────────────────────────┐
        │   Агент 3: Socratic Mentor Loop   │ ◄───► [Песочница: curriculum/sandbox]
        │        (core/mentor_agent)        │ ◄───► [Студент в UI Streamlit]
        └───────────────────────────────────┘
```

### Структура репозитория

```text
hackalem_edu_agent/
├── .cursorrules               # Инструкции для AI-ассистентов в IDE
├── pyproject.toml             # Манифест зависимостей uv (Python 3.11+)
├── README.md                  # Полная спецификация проекта
│
├── core/                      # ОРКЕСТРАЦИЯ И МЕНТОР (Ты: Lead Architect)
│   ├── state.py               # Состояние конвейера (PipelineSessionState)
│   ├── orchestrator.py        # LangGraph граф переходов
│   └── mentor_agent.py        # ReAct-цикл Сократического тьютора
│
├── ingestion/                 # ПАРСИНГ МАТЕРИАЛОВ (Напарник 1: Data Engineer)
│   ├── parser_agent.py        # Маршрутизатор парсинга файлов
│   ├── document_parsers.py    # Экстракторы PDF, DOCX, PPTX, TeX, MD
│   └── vision_ocr.py          # Распознавание формул и схем через Vision API
│
├── curriculum/                # АРХИТЕКТУРА КУРСА И ПЕСОЧНИЦА (Напарник 1 + Ты)
│   ├── architect_agent.py     # Генератор конспектов и квизов (Structured Outputs)
│   ├── schemas.py             # Pydantic-модели (CurriculumSchema, QuizItem)
│   └── sandbox.py             # Изолированный запуск Python-кода (subprocess)
│
├── app/                       # FASTAPI БЭКЕНД (Ты: Lead Architect)
│   └── main.py                # REST API + SSE-стриминг промежуточных мыслей
│
├── ui/                        # ИНТЕРФЕЙС И ДЕМО (Напарник 2: Frontend & Pitch)
│   ├── app.py                 # Streamlit UI с 3-шаговым степпером
│   └── components.py          # Виджеты логов reasoning и редактор кода
│
└── data/sample_materials/     # Заготовленные тестовые материалы
```

---

## 3. Распределение Ролей и Технические Задания

### 👤 Участник 1 (Саня): Pipeline Lead & Mentor Architect
- **Зона:** `core/`, `app/`.
- **Задачи:**
  1. Реализовать состояние `PipelineSessionState` и связать узлы пайплайна в LangGraph (`core/orchestrator.py`).
  2. Реализовать асинхронный сократический цикл `core/mentor_agent.py` с поддержкой вызова песочницы (`sandbox.py`) и стримингом мыслей (`thought_logs`).
  3. Развернуть сервер FastAPI (`app/main.py`) со стримингом событий через Server-Sent Events (SSE).

**Промпт для Codex/ChatGPT:**
```text
Act as a Principal AI Systems Architect. Implement `core/state.py` and `core/orchestrator.py` using LangGraph.
Stack: Python 3.11, LangGraph, Pydantic v2.

Requirements:
1. In `core/state.py`, define `PipelineSessionState(TypedDict)` with fields:
   - raw_file_bytes: Optional[bytes]
   - file_type: str
   - parsed_content: str
   - lesson_plan: Optional[dict]
   - chat_history: list[dict]
   - student_input: str
   - mentor_response: str
   - thought_logs: list[str]
2. In `core/orchestrator.py`, build a LangGraph `StateGraph`:
   - Node 1 `ingest_node`: calls `ingestion.parser_agent.run_ingestion`.
   - Node 2 `curriculum_node`: calls `curriculum.architect_agent.generate_curriculum`.
   - Wire: entry -> ingest_node -> curriculum_node -> END.
   - Provide helper `process_uploaded_document(file_bytes: bytes, file_type: str) -> dict`.
Ensure complete, typed Python code with error handling.
```

---

### 👤 Участник 2 (Артем): Data Ingestion & Curriculum Engineer
- **Зона:** `ingestion/`, `curriculum/`.
- **Задачи:**
  1. Реализовать `ingestion/document_parsers.py` для извлечения текста из PDF (`pypdf`), DOCX (`python-docx`), PPTX (`python-pptx`), TeX и MD.
  2. Реализовать `ingestion/vision_ocr.py` для распознавания формул (LaTeX) и диаграмм с картинок через OpenAI Vision (`gpt-4o-mini`).
  3. Создать `curriculum/architect_agent.py` для генерации конспекта и практических задач со строгой схемой Pydantic (`client.beta.chat.completions.parse`).
  4. Создать безопасную песочницу `curriculum/sandbox.py` с ограничением времени выполнения в 5 секунд.

**Промпт для Codex/ChatGPT:**
```text
Act as a Python Systems & Data Engineer. Implement `ingestion/document_parsers.py` and `curriculum/sandbox.py`.
Requirements:
1. In `ingestion/document_parsers.py`:
   - Implement functions to extract text from PDF (pypdf), DOCX (python-docx), PPTX (python-pptx), and plain text files (TeX, MD).
   - Return clean Markdown with preserved headers.
2. In `curriculum/sandbox.py`:
   - Implement `execute_code(code: str, timeout_seconds: int = 5) -> dict`.
   - Run code using subprocess with a hard 5-second timeout.
   - Block dangerous operations via AST checks (e.g. imports of os, sys, shutil, socket).
   - Capture stdout, stderr, and execution time. Return format: {"success": bool, "stdout": str, "stderr": str}.
```

---

### 👤 Участник 3 (Даня): Frontend & Pitch Lead
- **Зона:** `ui/`, подготовка питча.
- **Задачи:**
  1. Разработать интерфейс `ui/app.py` на Streamlit с визуализацией трех шагов:
     - Шаг 1: Загрузка документа любого формата.
     - Шаг 2: Карточка конспекта и выбор практической концепции.
     - Шаг 3: Чат со тьютором, редактор кода и раскрывающийся статус рассуждений (`st.status`).
  2. Подготовить 3-минутный питч-дек (7 слайдов) и отрепетировать демонстрационный сценарий (Live Demo).

**Промпт для Codex/ChatGPT:**
```text
Act as a Senior Streamlit Developer. Implement `ui/app.py` and `ui/components.py`.
Requirements:
1. Layout:
   - Sidebar: Upload area for PDF/DOCX/PPTX/Images and button "⚡ Построить курс".
   - Main area - Step 1: Display structured summary & key concepts from Agent 2.
   - Main area - Step 2: Socratic Chat (`st.chat_message`) with integrated code editor (`st.text_area`) and submit button.
   - Observability: For each assistant turn, display `st.status("🧠 Ход рассуждений агента")` containing tool calls and sandbox execution logs.
2. Persist state in `st.session_state` (chat history, curriculum plan, mastery score).
```

---

## 4. Быстрый Старт

```bash
# 1. Установка зависимостей через uv
uv sync

# 2. Настройка переменных окружения
cp .env.example .env
# Заполните OPENAI_API_KEY в файле .env

# 3. Запуск веб-интерфейса Streamlit
uv run streamlit run ui/app.py
```