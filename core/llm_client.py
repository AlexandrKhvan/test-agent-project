# core/llm_client.py
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

def get_async_llm_client() -> tuple[AsyncOpenAI, str]:
    """
    Возвращает клиент и имя модели.
    Автоматически переключается между Gemini (бесплатно) и OpenAI (под грант).
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY не задан в .env файле!")
        
        # Эндпоинт Google AI Studio, полностью совместимый со спецификацией OpenAI
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        model = os.getenv("LLM_MODEL", "gemini-3.6-flash")
        return client, model
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не задан в .env файле!")
        client = AsyncOpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
        return client, model