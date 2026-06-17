from __future__ import annotations

from typing import Any

import httpx
from langchain_core.language_models import BaseChatModel

from student_success_assistant.core.config import get_settings


def _make_http_client() -> httpx.Client:
    try:
        import pip_system_certs  # noqa: F401
    except ImportError:
        pass
    return httpx.Client(verify=False)


def get_chat_llm(model: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> BaseChatModel | None:
    settings = get_settings()
    provider = settings.llm_provider
    resolved_model = model or settings.llm_model
    resolved_temp = temperature if temperature is not None else settings.llm_temperature

    if provider == "openai":
        if not settings.openai_api_key:
            return None
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            return None
        kwargs = dict(
            model=resolved_model,
            api_key=settings.openai_api_key,
            temperature=resolved_temp,
            http_client=_make_http_client(),
        )
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
            if "openrouter" in settings.openai_base_url:
                kwargs["default_headers"] = {
                    "HTTP-Referer": "https://github.com/anomalyco/opencode",
                    "X-Title": "Student Success Assistant",
                }
        return ChatOpenAI(**kwargs, timeout=120)

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            return None
        return ChatOllama(
            model=resolved_model,
            base_url=settings.ollama_base_url,
            temperature=resolved_temp,
            request_timeout=120,
        )

    return None
