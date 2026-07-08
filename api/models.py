from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RAGRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    k: int = Field(default=5, ge=1, le=10)


class Citation(BaseModel):
    chunk_id: str
    source_name: str
    reference: str
    topic: str
    source_page: int | None = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    topic: str
    reference: str
    score: float
    text_preview: str


class RAGResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float = Field(..., ge=0.0, le=1.0)
    retrieved_chunks: list[RetrievedChunk]
    disclaimer: str


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    dependencies: dict[str, dict[str, Any]]
