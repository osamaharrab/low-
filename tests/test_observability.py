import pytest

pytest.importorskip("pydantic")
pytest.importorskip("prometheus_client")
pytest.importorskip("starlette")

from api.models import Citation, RAGResponse, RetrievedChunk
from api.observability import (
    INFLIGHT_REQUESTS,
    RAG_ANSWERS_TOTAL,
    RAG_GENERATION_ERRORS_TOTAL,
    REQUEST_LATENCY_SECONDS,
    REQUESTS_TOTAL,
    log_json,
    safe_metric_path,
)


def test_metric_objects_exist_with_expected_names():
    assert REQUESTS_TOTAL._name == "requests"
    assert REQUEST_LATENCY_SECONDS._name == "request_latency_seconds"
    assert INFLIGHT_REQUESTS._name == "inflight_requests"
    assert RAG_ANSWERS_TOTAL._name == "rag_answers"
    assert RAG_GENERATION_ERRORS_TOTAL._name == "rag_generation_errors"


def test_log_json_and_safe_path_do_not_crash():
    assert safe_metric_path("/rag/answer") == "/rag/answer"
    assert safe_metric_path("/unknown") == "other"
    log_json({"ts": "test", "level": "info", "request_id": "abc", "path": "/healthz"})


def test_rag_response_model_accepts_expected_shape():
    response = RAGResponse(
        answer="إجابة عربية مختصرة",
        citations=[
            Citation(
                chunk_id="c1",
                source_name="source",
                reference="ref",
                topic="topic",
                source_page=None,
            )
        ],
        confidence=0.8,
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                topic="topic",
                reference="ref",
                score=0.8,
                text_preview="preview",
            )
        ],
        disclaimer="disclaimer",
    )

    assert response.citations[0].chunk_id == "c1"
    assert response.retrieved_chunks[0].score == 0.8
