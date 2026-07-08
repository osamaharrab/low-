from __future__ import annotations

import re

import httpx

from api.settings import Settings


INSUFFICIENT_ANSWER = "لا تكفي قاعدة المعرفة الحالية للإجابة بثقة."

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", flags=re.IGNORECASE | re.DOTALL)
THINK_TAG_RE = re.compile(r"</?think>", flags=re.IGNORECASE)


class GeneratorError(RuntimeError):
    """Raised when Ollama is unreachable or returns an unusable response."""


def clean_llm_output(text: str | None) -> str:
    cleaned = THINK_BLOCK_RE.sub("", text or "")
    cleaned = THINK_TAG_RE.sub("", cleaned)
    cleaned = cleaned.strip()
    return cleaned or INSUFFICIENT_ANSWER


def generate_answer(system_prompt: str, user_prompt: str, settings: Settings) -> str:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
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
    return clean_llm_output(message.get("content"))
