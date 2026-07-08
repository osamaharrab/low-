from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


REQUESTS_TOTAL = Counter("requests_total", "HTTP requests by path and status.", ["path", "status"])
REQUEST_LATENCY_SECONDS = Histogram("request_latency_seconds", "HTTP request latency by path.", ["path"])
INFLIGHT_REQUESTS = Gauge("inflight_requests", "In-flight HTTP requests.")
RAG_ANSWERS_TOTAL = Counter("rag_answers_total", "RAG answers by outcome.", ["outcome"])
RAG_RETRIEVED_CHUNKS = Histogram("rag_retrieved_chunks", "Number of retrieved chunks per RAG request.")
RAG_GENERATION_ERRORS_TOTAL = Counter("rag_generation_errors_total", "RAG generation errors.")

KNOWN_PATHS = {"/healthz", "/readyz", "/metrics", "/rag/answer"}
LOGGER = logging.getLogger("lawz_ai_jo")

if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_metric_path(path: str) -> str:
    return path if path in KNOWN_PATHS else "other"


def log_json(event: dict[str, Any]) -> None:
    LOGGER.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class MetricsLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        path = safe_metric_path(request.url.path)
        status = 500
        request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        INFLIGHT_REQUESTS.inc()
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            latency_seconds = time.perf_counter() - start
            INFLIGHT_REQUESTS.dec()
            REQUEST_LATENCY_SECONDS.labels(path=path).observe(latency_seconds)
            REQUESTS_TOTAL.labels(path=path, status=str(status)).inc()
            log_json(
                {
                    "ts": utc_now_iso(),
                    "level": "info",
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "latency_ms": round(latency_seconds * 1000, 2),
                }
            )


def setup_observability(app) -> None:
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(MetricsLoggingMiddleware)
    app.mount("/metrics", make_asgi_app())
