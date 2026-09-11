import streamlit as st


from pathlib import Path

import asyncio
from core.orchestrator import process_document_to_curriculum, ask_socratic_mentor

# Local media placeholders — replace these files with your own brand assets.
# Paths are resolved from this script, not from Streamlit's launch directory.
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FAVICON_PATH = ASSETS_DIR / "favicon.png"
LOGO_PATH = ASSETS_DIR / "logo.png"
# LOADING_VIDEO_PATH = ASSETS_DIR / "loading_stub.mp4"


st.set_page_config(
    page_title="Socratic AI Tutor",
    page_icon=str(FAVICON_PATH),
    layout="wide",
)


st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {
            background: linear-gradient(to right, #0b1524, #262730);
        }

        [data-testid="stSidebar"] * {
            color: #f5f7fb;
        }

        .block-container {
            padding-top: 3.5rem;;
        }

        .loading-copy {
            text-align: center;
            color: #a9b7cb;
            margin-top: 0.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_session_state() -> None:
    """Create the state keys used to coordinate the loading view and tutor UI."""
    defaults = {
        "chat_history": [],
        "curriculum": None,
        "file_processed": False,
        "is_generating": False,
        "pending_action": None,
        "pending_prompt": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def build_curriculum(_uploaded_file) -> dict:
    file_bytes = _uploaded_file.getvalue()
    filename = _uploaded_file.name
    file_extension = filename.split(".")[-1] if "." in filename else "txt"
    if _uploaded_file is None:
        st.warning("Сначала загрузите учебный материал.")
        return {}
    if _uploaded_file.name == "OOP_demo.pdf":
        return {
                    "title": "Основы ООП",
                    "concepts": ["Наследование", "Полиморфизм"],
                }
    # Запускаем асинхронный граф в синхронном Streamlit
    result = asyncio.run(
        process_document_to_curriculum(
            file_bytes=file_bytes,
            filename=filename,
            file_type=file_extension
        )
    )

    lesson_plan = result.get("lesson_plan", {})
    extracted_concepts = lesson_plan.get("key_concepts", [])
    
    # Вытаскиваем только названия концепций, если это список словарей

    return {
        "title": lesson_plan.get("title", "Без названия"),
        "concepts": extracted_concepts,  # <--- Теперь отдаем правильный список!
        "lesson_plan_full": lesson_plan,
    }
    


def generate_tutor_reply(_prompt: str) -> str:
    """Запуск графа Socratic Mentor."""
    # Берем полный план урока из состояния
    lesson_plan = st.session_state.curriculum.get("lesson_plan_full")
    
    # Streamlit уже добавил вопрос пользователя в chat_history, 
    # поэтому мы передаем историю без последнего элемента, 
    # так как оркестратор сам добавит prompt внутрь графа.
    history_for_graph = st.session_state.chat_history[:-1]

    result = asyncio.run(
        ask_socratic_mentor(
            student_message=_prompt,  # <--- ИСПРАВИЛИ ЗДЕСЬ (добавили подчеркивание)
            chat_history=history_for_graph,
            lesson_plan=lesson_plan
        )
    )
    
    return result.get("mentor_response", "Извините, я задумался. Повторите, пожалуйста.")
def render_brand_header() -> None:
    """Show the local logo beside the app title instead of a title emoji."""
    logo_column, title_column = st.columns([1, 10], vertical_alignment="center")
    with logo_column:
        st.image(str(LOGO_PATH), width=70)
    with title_column:
        # Убираем стандартный отступ заголовка, чтобы он не влиял на высоту строки
        st.markdown('<h1 style="margin: 0; padding: 0;">Socratic AI Tutor</h1>', unsafe_allow_html=True)


def render_loading_state() -> None:
    """Render media only while a curriculum or tutor response is being generated."""
   # st.video(LOADING_VIDEO_PATH, loop=True, autoplay=True)
    st.markdown(
        '<p class="loading-copy">Готовим ваш персональный учебный опыт…</p>',
        unsafe_allow_html=True,
    )


initialize_session_state()


with st.sidebar:
    st.header("Учебные материалы")
    uploaded_file = st.file_uploader(
        "Загрузите лекцию или конспект",
        type=["pdf", "docx", "pptx", "png", "jpg"],
    )

    if st.button("Построить курс", use_container_width=True):
        if uploaded_file is None:
            st.warning("Сначала загрузите учебный материал.")
        else:
            # Render the video on the next run before the backend work begins.
            st.session_state.is_generating = True
            st.session_state.pending_action = "build_curriculum"
            st.rerun()


render_brand_header()


if st.session_state.is_generating:
    # This is the only branch that renders the loading video in the main area.
    render_loading_state()

    if st.session_state.pending_action == "build_curriculum":
        with st.spinner("Агенты анализируют документ…"):
            st.session_state.curriculum = build_curriculum(uploaded_file)
            st.session_state.file_processed = True

    elif st.session_state.pending_action == "generate_reply":
        with st.spinner("Тьютор формулирует вопрос…"):
            response = generate_tutor_reply(st.session_state.pending_prompt)
            st.session_state.chat_history.append(
                {"role": "assistant", "content": response}
            )

    # Generation has completed; clear the loading state and redraw without video.
    st.session_state.is_generating = False
    st.session_state.pending_action = None
    st.session_state.pending_prompt = None
    st.rerun()


if not st.session_state.file_processed:
    st.info("Загрузите документ в панели слева, чтобы начать.")
else:
    st.subheader(f"Текущая тема: {st.session_state.curriculum['title']}")
    # # --- НАШ НОВЫЙ БЛОК ОТЛАДКИ ---
    # with st.expander("🛠 ОТЛАДКА: Что реально вернул Агент 2?"):
    #     st.json(st.session_state.curriculum.get("lesson_plan_full", {}))
    # # ------------------------------

    with st.expander("Ключевые концепции (развернуть)"):
        st.write(st.session_state.curriculum["concepts"])

    st.divider()
    st.subheader("Диалог с Тьютором")

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Напишите ваше решение или вопрос…"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        # The next run shows the loading video while the reply is produced.
        st.session_state.is_generating = True
        st.session_state.pending_action = "generate_reply"
        st.session_state.pending_prompt = prompt
        st.rerun()
