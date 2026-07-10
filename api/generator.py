from __future__ import annotations

import re
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from api.settings import Settings


INSUFFICIENT_ANSWER = "لا تكفي قاعدة المعرفة الحالية للإجابة بثقة."

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", flags=re.IGNORECASE | re.DOTALL)
THINK_TAG_RE = re.compile(r"</?think>", flags=re.IGNORECASE)


class GeneratorError(RuntimeError):
    """Raised when the configured LLM provider is unavailable or unusable."""


def clean_llm_output(text: str | None) -> str:
    cleaned = THINK_BLOCK_RE.sub("", text or "")
    cleaned = THINK_TAG_RE.sub("", cleaned)
    cleaned = cleaned.strip()
    return cleaned or INSUFFICIENT_ANSWER


def _provider_name(settings: Settings) -> str:
    return (settings.llm_provider or "ollama").strip().lower()


def _has_groq_api_key(settings: Settings) -> bool:
    api_key = (settings.groq_api_key or "").strip()
    return bool(api_key) and api_key != "your_groq_api_key_here"


def _generate_with_ollama(system_prompt: str, user_prompt: str, settings: Settings) -> str:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": settings.llm_temperature,
            "top_p": 0.9,
        },
    }

    try:
        response = httpx.post(url, json=payload, timeout=settings.ollama_timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GeneratorError(str(exc)) from exc

    message = data.get("message") or {}
    return str(message.get("content") or "")


def _generate_with_groq(system_prompt: str, user_prompt: str, settings: Settings) -> str:
    if not _has_groq_api_key(settings):
        raise GeneratorError("GROQ_API_KEY is required when LLM_PROVIDER=groq")

    url = f"{settings.groq_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key.strip()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=settings.llm_timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GeneratorError(str(exc)) from exc

    try:
        choices = data["choices"]
        message = choices[0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GeneratorError("Groq returned an unusable response") from exc

    return str(message.get("content") or "")


def generate_answer(system_prompt: str, user_prompt: str, settings: Settings) -> str:
    provider = _provider_name(settings)
    if provider == "groq":
        answer = _generate_with_groq(system_prompt, user_prompt, settings)
    elif provider == "ollama":
        answer = _generate_with_ollama(system_prompt, user_prompt, settings)
    else:
        raise GeneratorError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

    return clean_llm_output(answer)
