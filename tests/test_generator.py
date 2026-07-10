import pytest
from types import SimpleNamespace

pytest.importorskip("httpx")

from api.generator import GeneratorError, clean_llm_output, generate_answer


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def make_settings(**overrides):
    values = {
        "llm_provider": "ollama",
        "groq_api_key": "",
        "groq_base_url": "https://api.groq.com/openai/v1",
        "groq_model": "llama-3.3-70b-versatile",
        "llm_timeout_seconds": 30,
        "llm_temperature": 0.1,
        "llm_max_tokens": 650,
        "ollama_base_url": "http://host.docker.internal:11434",
        "ollama_model": "qwen3:4b",
        "ollama_timeout_seconds": 120,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_clean_llm_output_removes_think_blocks():
    cleaned = clean_llm_output("<think>hidden reasoning</think>\nإجابة مختصرة")

    assert cleaned == "إجابة مختصرة"


def test_generate_answer_rejects_unsupported_provider():
    settings = make_settings(llm_provider="unsupported")

    with pytest.raises(GeneratorError, match="Unsupported LLM_PROVIDER"):
        generate_answer("system", "user", settings)


def test_groq_provider_requires_api_key():
    settings = make_settings(llm_provider="groq", groq_api_key="")

    with pytest.raises(GeneratorError, match="GROQ_API_KEY is required"):
        generate_answer("system", "user", settings)


def test_groq_response_parsing_uses_chat_completions(monkeypatch):
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return FakeResponse({"choices": [{"message": {"content": "<think>x</think>\nإجابة Groq"}}]})

    monkeypatch.setattr("api.generator.httpx.post", fake_post)
    settings = make_settings(
        llm_provider="groq",
        groq_api_key="test-key",
        groq_base_url="https://api.groq.com/openai/v1",
        groq_model="llama-3.3-70b-versatile",
        llm_temperature=0.2,
        llm_max_tokens=321,
        llm_timeout_seconds=12,
    )

    answer = generate_answer("system prompt", "user prompt", settings)

    assert answer == "إجابة Groq"
    assert calls["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert calls["kwargs"]["headers"]["Authorization"] == "Bearer test-key"
    assert calls["kwargs"]["json"]["model"] == "llama-3.3-70b-versatile"
    assert calls["kwargs"]["json"]["temperature"] == 0.2
    assert calls["kwargs"]["json"]["max_tokens"] == 321
    assert calls["kwargs"]["timeout"] == 12


def test_ollama_response_parsing_still_works(monkeypatch):
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return FakeResponse({"message": {"content": "إجابة محلية"}})

    monkeypatch.setattr("api.generator.httpx.post", fake_post)
    settings = make_settings(
        llm_provider="ollama",
        ollama_base_url="http://ollama:11434",
        ollama_model="qwen3:4b",
        ollama_timeout_seconds=42,
        llm_temperature=0.2,
    )

    answer = generate_answer("system prompt", "user prompt", settings)

    assert answer == "إجابة محلية"
    assert calls["url"] == "http://ollama:11434/api/chat"
    assert calls["kwargs"]["json"]["model"] == "qwen3:4b"
    assert calls["kwargs"]["json"]["options"]["temperature"] == 0.2
    assert calls["kwargs"]["timeout"] == 42
