from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import Settings, get_settings
from api.generator import GeneratorError, INSUFFICIENT_ANSWER
from api.models import HealthResponse, RAGRequest, RAGResponse
from api.observability import (
    RAG_ANSWERS_TOTAL,
    RAG_GENERATION_ERRORS_TOTAL,
    RAG_RETRIEVED_CHUNKS,
    setup_observability,
)
from api.rag import answer_question


SERVICE_NAME = "lawz-ai-jo-api"


def check_weaviate_ready(settings: Settings) -> dict[str, object]:
    url = f"{settings.weaviate_url.rstrip('/')}/v1/.well-known/ready"
    try:
        response = httpx.get(url, timeout=3)
        return {
            "ok": response.status_code == 200,
            "url": url,
            "status_code": response.status_code,
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def check_ollama_ready(settings: Settings) -> dict[str, object]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        response = httpx.get(url, timeout=3)
        return {
            "ok": response.status_code == 200,
            "url": url,
            "status_code": response.status_code,
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def check_xai_ready(settings: Settings) -> dict[str, object]:
    api_key = (settings.xai_api_key or "").strip()
    api_key_configured = bool(api_key) and api_key != "your_xai_api_key_here"
    config_present = bool((settings.xai_base_url or "").strip()) and bool((settings.xai_model or "").strip())
    ok = api_key_configured and config_present
    payload: dict[str, object] = {
        "ok": ok,
        "provider": "xai",
        "base_url": settings.xai_base_url.rstrip("/"),
        "model": settings.xai_model,
        "api_key_configured": api_key_configured,
        "config_present": config_present,
    }
    if not ok:
        payload["error"] = "xAI provider is not fully configured."
    return payload


def check_llm_ready(settings: Settings) -> dict[str, object]:
    provider = (settings.llm_provider or "ollama").strip().lower()
    if provider == "ollama":
        result = check_ollama_ready(settings)
        result["provider"] = "ollama"
        result["model"] = settings.ollama_model
        return result
    if provider in {"xai", "grok"}:
        return check_xai_ready(settings)
    return {
        "ok": False,
        "provider": provider,
        "error": f"Unsupported LLM_PROVIDER: {settings.llm_provider}",
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Lawz AI JO", version="0.1.0")
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin, "http://localhost:3001"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    setup_observability(app)

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok", service=SERVICE_NAME)

    @app.get("/readyz")
    def readyz(settings: Settings = Depends(get_settings)):
        dependencies = {
            "weaviate": check_weaviate_ready(settings),
            "llm": check_llm_ready(settings),
        }
        ready = all(bool(item.get("ok")) for item in dependencies.values())
        payload = {
            "status": "ok" if ready else "not_ready",
            "service": SERVICE_NAME,
            "dependencies": dependencies,
        }
        if not ready:
            return JSONResponse(status_code=503, content=payload)
        return payload

    @app.post("/rag/answer", response_model=RAGResponse)
    def rag_answer(request: RAGRequest, settings: Settings = Depends(get_settings)) -> RAGResponse:
        try:
            response = answer_question(request.question, request.k, settings)
        except GeneratorError as exc:
            RAG_ANSWERS_TOTAL.labels(outcome="error").inc()
            RAG_GENERATION_ERRORS_TOTAL.inc()
            raise HTTPException(status_code=503, detail=f"LLM provider unavailable: {exc}") from exc
        except Exception:
            RAG_ANSWERS_TOTAL.labels(outcome="error").inc()
            raise

        outcome = "abstained" if INSUFFICIENT_ANSWER in response.answer else "answered"
        RAG_ANSWERS_TOTAL.labels(outcome=outcome).inc()
        RAG_RETRIEVED_CHUNKS.observe(len(response.retrieved_chunks))
        return response

    return app


app = create_app()
