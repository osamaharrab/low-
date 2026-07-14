from __future__ import annotations

import httpx
import anyio

from api.main import app


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeAsyncClient:
    response = None
    error = None
    calls = {}

    def __init__(self, **kwargs):
        self.calls["client_kwargs"] = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        self.calls["url"] = url
        self.calls["kwargs"] = kwargs
        if self.error:
            raise self.error
        return self.response


def patch_translate_client(monkeypatch, response=None, error=None):
    FakeAsyncClient.response = response
    FakeAsyncClient.error = error
    FakeAsyncClient.calls = {}
    monkeypatch.setattr("api.translation._create_async_client", lambda timeout: FakeAsyncClient(timeout=timeout))
    return FakeAsyncClient.calls


def post_translate(payload):
    async def run_request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/translate", json=payload)

    return anyio.run(run_request)


def test_translate_success_uses_libretranslate_without_api_key(monkeypatch):
    calls = patch_translate_client(
        monkeypatch,
        response=FakeResponse({"translatedText": "The worker may terminate the contract in cases set by law."}),
    )

    response = post_translate({"text": "يجوز للعامل إنهاء العقد في الحالات التي يحددها القانون."})

    assert response.status_code == 200
    assert response.json() == {"translated_text": "The worker may terminate the contract in cases set by law."}
    assert calls["url"].endswith("/translate")
    assert calls["kwargs"]["json"] == {
        "q": "يجوز للعامل إنهاء العقد في الحالات التي يحددها القانون.",
        "source": "ar",
        "target": "en",
        "format": "text",
    }
    assert "headers" not in calls["kwargs"]
    assert "api_key" not in calls["kwargs"]["json"]


def test_translate_rejects_empty_input():
    response = post_translate({"text": "   "})

    assert response.status_code == 422


def test_translate_unavailable_returns_503(monkeypatch):
    patch_translate_client(monkeypatch, error=httpx.TimeoutException("timed out"))

    response = post_translate({"text": "نص عربي"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Translation service is temporarily unavailable."


def test_translate_invalid_upstream_response_returns_502(monkeypatch):
    patch_translate_client(monkeypatch, response=FakeResponse({"unexpected": "shape"}))

    response = post_translate({"text": "نص عربي"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Translation service returned an invalid response."


def test_translate_endpoint_does_not_call_rag_or_kg(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("RAG/KG pipeline must not be called by /translate")

    monkeypatch.setattr("api.main.answer_question", explode)
    monkeypatch.setattr("api.main.query_knowledge_graph", explode)
    patch_translate_client(monkeypatch, response=FakeResponse({"translatedText": "English text."}))

    response = post_translate({"text": "نص عربي"})

    assert response.status_code == 200
    assert response.json()["translated_text"] == "English text."
