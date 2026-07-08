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
            "ollama": check_ollama_ready(settings),
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
            raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc
        except Exception:
            RAG_ANSWERS_TOTAL.labels(outcome="error").inc()
            raise

        outcome = "abstained" if INSUFFICIENT_ANSWER in response.answer else "answered"
        RAG_ANSWERS_TOTAL.labels(outcome=outcome).inc()
        RAG_RETRIEVED_CHUNKS.observe(len(response.retrieved_chunks))
        return response

    return app


app = create_app()
