from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class KGRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)


class KGNode(BaseModel):
    id: str
    labels: list[str]
    properties: dict[str, Any]


class KGRelationship(BaseModel):
    id: str
    type: str
    source: str
    target: str
    properties: dict[str, Any]


class KGResponse(BaseModel):
    answer: str
    generated_cypher: str
    parameters: dict[str, Any]
    records: list[dict[str, Any]]
    nodes: list[KGNode]
    relationships: list[KGRelationship]
    row_count: int = Field(..., ge=0)
    disclaimer: str


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    dependencies: dict[str, dict[str, Any]]


class TranslateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=12000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Translation text must not be empty.")
        return stripped


class TranslateResponse(BaseModel):
    translated_text: str
