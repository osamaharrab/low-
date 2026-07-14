from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HELDOUT = REPO_ROOT / "eval" / "heldout.jsonl"
DEFAULT_SEED_CHUNKS = REPO_ROOT / "api" / "seed_chunks.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "results"
DEFAULT_REPORT_DIR = REPO_ROOT / "eval"

WEAVIATE_CLASS = "LegalChunk"
DEFAULT_API_URL = "http://localhost:8001"
DEFAULT_WEAVIATE_URL = "http://localhost:8081"
DEFAULT_SEEDS = [42, 1337, 2024]

ANSWERABLE_CATEGORIES = [
    "contracts_probation_flexible_work",
    "termination_notice_unfair_dismissal",
    "wages_deductions_overtime",
    "leave_hours_weekly_rest",
    "worker_protection_safety_social_security",
]
ABSTENTION_CATEGORIES = {
    "out_of_scope": 5,
    "insufficient_facts": 5,
}
ALLOWED_STATUSES = {"pending", "approved", "rejected"}
REQUIRED_TOP_LEVEL_FIELDS = {
    "id",
    "question",
    "expected_behavior",
    "gold_answer",
    "required_points",
    "expected_chunk_ids",
    "expected_references",
    "metadata",
    "validation",
}
REQUIRED_METADATA_FIELDS = {"category", "difficulty", "question_style"}

BASELINE_PROPERTIES = [
    "chunk_id",
    "source_name",
    "reference",
    "topic",
    "text",
    "source_page",
    "source_type",
    "jurisdiction",
]
BASELINE_SEARCH_PROPERTIES = ["topic", "reference", "source_name", "text"]
BASELINE_TEMPLATE = "وفقًا للمصدر القانوني المسترجع:"

INSUFFICIENT_PHRASES = (
    "لا تكفي قاعدة المعرفة",
    "لا تكفي قاعدة المعرفه",
    "لا توجد معلومات كافية",
    "لا توجد معلومات كافيه",
    "السياق غير كاف",
    "لا أستطيع الإجابة بثقة",
    "لا استطيع الاجابة بثقة",
    "لا استطيع الاجابه بثقه",
)

ARABIC_VARIANTS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
    }
)
DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")
WHITESPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^\w\u0600-\u06FF]+", flags=re.UNICODE)


class EvaluationError(RuntimeError):
    """Raised for actionable evaluation setup, validation, or aggregation errors."""


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load a UTF-8 JSONL file and require each row to be a JSON object."""
    source = Path(path)
    rows: list[dict[str, Any]] = []
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvaluationError(f"Could not read {source}: {exc}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluationError(f"{source}:{line_number} is not valid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise EvaluationError(f"{source}:{line_number} must be a JSON object.")
        rows.append(row)
    return rows


def write_jsonl_atomic(path: str | Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL with a same-directory temporary file then atomic replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    temp.write_text(text, encoding="utf-8")
    temp.replace(target)


def write_text_atomic(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(target)


def write_json_atomic(path: str | Path, data: dict[str, Any]) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_seed_chunks(path: str | Path = DEFAULT_SEED_CHUNKS) -> dict[str, dict[str, Any]]:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Could not read seed chunks from {source}: {exc}") from exc
    if not isinstance(data, list):
        raise EvaluationError(f"{source} must contain a JSON array.")

    chunks: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(data, start=1):
        if not isinstance(row, dict):
            raise EvaluationError(f"{source}: row {index} must be an object.")
        chunk_id = str(row.get("chunk_id") or "").strip()
        if not chunk_id:
            raise EvaluationError(f"{source}: row {index} is missing chunk_id.")
        chunks[chunk_id] = row
    return chunks


def normalize_text(text: str) -> str:
    normalized = (text or "").strip().translate(ARABIC_VARIANTS)
    normalized = DIACRITICS_RE.sub("", normalized)
    normalized = PUNCT_RE.sub(" ", normalized)
    return WHITESPACE_RE.sub(" ", normalized).strip().lower()


def normalize_answer(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return WHITESPACE_RE.sub(" ", normalized).strip()


def bool_to_cell(value: bool | None) -> str:
    if value is True:
        return "1"
    if value is False:
        return "0"
    return ""


def cell_to_bool(row: dict[str, str], field: str) -> bool | None:
    value = (row.get(field) or "").strip()
    if value == "1":
        return True
    if value == "0":
        return False
    return None


def rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def population_std(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[low])
    return float(ordered[low] + (ordered[high] - ordered[low]) * (rank - low))


def validate_heldout_rows(
    rows: list[dict[str, Any]],
    seed_chunks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Validate held-out fixture structure, distributions, and seed references."""
    errors: list[str] = []
    warnings: list[str] = []

    ids = [str(row.get("id") or "") for row in rows]
    expected_ids = [f"lawz-{index:03d}" for index in range(1, 51)]
    behavior_counts = Counter(str(row.get("expected_behavior") or "") for row in rows)
    category_counts = Counter()
    difficulty_counts = Counter()
    style_counts = Counter()
    status_counts = Counter()
    answerable_category_counts = Counter()
    abstention_category_counts = Counter()
    normalized_questions: dict[str, str] = {}

    if len(rows) != 50:
        errors.append(f"Expected exactly 50 examples, found {len(rows)}.")
    if len(set(ids)) != len(ids):
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        errors.append(f"Duplicate IDs found: {', '.join(duplicates)}.")
    if ids != expected_ids:
        errors.append("IDs must be sequential and exactly lawz-001 through lawz-050.")

    for index, row in enumerate(rows, start=1):
        row_id = str(row.get("id") or f"row-{index}")
        missing = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(row))
        if missing:
            errors.append(f"{row_id}: missing top-level fields: {', '.join(missing)}.")
            continue

        question = row.get("question")
        if not isinstance(question, str) or not question.strip():
            errors.append(f"{row_id}: question must be a non-empty string.")
        else:
            normalized = normalize_text(question)
            previous = normalized_questions.get(normalized)
            if previous:
                errors.append(f"{row_id}: duplicate normalized question also used by {previous}.")
            normalized_questions[normalized] = row_id

        behavior = row.get("expected_behavior")
        if behavior not in {"answer", "abstain"}:
            errors.append(f"{row_id}: expected_behavior must be 'answer' or 'abstain'.")

        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            errors.append(f"{row_id}: metadata must be an object.")
            metadata = {}
        missing_metadata = sorted(REQUIRED_METADATA_FIELDS - set(metadata))
        if missing_metadata:
            errors.append(f"{row_id}: missing metadata fields: {', '.join(missing_metadata)}.")
        category = str(metadata.get("category") or "")
        difficulty = str(metadata.get("difficulty") or "")
        style = str(metadata.get("question_style") or "")
        category_counts[category] += 1
        difficulty_counts[difficulty] += 1
        style_counts[style] += 1

        validation = row.get("validation")
        if not isinstance(validation, dict):
            errors.append(f"{row_id}: validation must be an object.")
            validation = {}
        status = validation.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{row_id}: validation.status must be one of {sorted(ALLOWED_STATUSES)}.")
        else:
            status_counts[str(status)] += 1
        reviewers = validation.get("reviewed_by")
        if not isinstance(reviewers, list):
            errors.append(f"{row_id}: validation.reviewed_by must be a list.")
        if not isinstance(validation.get("notes", ""), str):
            errors.append(f"{row_id}: validation.notes must be a string.")

        gold_answer = row.get("gold_answer")
        required_points = row.get("required_points")
        expected_chunk_ids = row.get("expected_chunk_ids")
        expected_references = row.get("expected_references")
        if not isinstance(required_points, list):
            errors.append(f"{row_id}: required_points must be a list.")
            required_points = []
        if not isinstance(expected_chunk_ids, list):
            errors.append(f"{row_id}: expected_chunk_ids must be a list.")
            expected_chunk_ids = []
        if not isinstance(expected_references, list):
            errors.append(f"{row_id}: expected_references must be a list.")
            expected_references = []

        if behavior == "answer":
            answerable_category_counts[category] += 1
            if category not in ANSWERABLE_CATEGORIES:
                errors.append(f"{row_id}: answerable category is not allowed: {category}.")
            if not isinstance(gold_answer, str) or not gold_answer.strip():
                errors.append(f"{row_id}: answerable example requires a non-empty gold_answer.")
            if not required_points or not all(isinstance(item, str) and item.strip() for item in required_points):
                errors.append(f"{row_id}: answerable example requires non-empty required_points.")
            if not expected_chunk_ids or not all(isinstance(item, str) and item.strip() for item in expected_chunk_ids):
                errors.append(f"{row_id}: answerable example requires expected_chunk_ids.")
            if not expected_references or not all(isinstance(item, str) and item.strip() for item in expected_references):
                errors.append(f"{row_id}: answerable example requires expected_references.")

            referenced_seed_refs: set[str] = set()
            for chunk_id in expected_chunk_ids:
                seed = seed_chunks.get(str(chunk_id))
                if seed is None:
                    errors.append(f"{row_id}: expected chunk_id does not exist in seed_chunks: {chunk_id}.")
                    continue
                referenced_seed_refs.add(str(seed.get("reference") or ""))
            for reference in expected_references:
                if str(reference) not in referenced_seed_refs:
                    errors.append(
                        f"{row_id}: expected reference does not exactly match an expected seed chunk reference: {reference}."
                    )

        if behavior == "abstain":
            abstention_category_counts[category] += 1
            if gold_answer is not None:
                errors.append(f"{row_id}: abstention example must have gold_answer null.")
            if required_points:
                errors.append(f"{row_id}: abstention example must have no required_points.")
            if expected_chunk_ids:
                errors.append(f"{row_id}: abstention example must have no expected_chunk_ids.")
            if expected_references:
                errors.append(f"{row_id}: abstention example must have no expected_references.")

    if behavior_counts.get("answer", 0) != 40:
        errors.append(f"Expected exactly 40 answer examples, found {behavior_counts.get('answer', 0)}.")
    if behavior_counts.get("abstain", 0) != 10:
        errors.append(f"Expected exactly 10 abstain examples, found {behavior_counts.get('abstain', 0)}.")
    for category in ANSWERABLE_CATEGORIES:
        if answerable_category_counts.get(category, 0) != 8:
            errors.append(
                f"Answerable category {category} must contain exactly 8 examples, "
                f"found {answerable_category_counts.get(category, 0)}."
            )
    for category, expected_count in ABSTENTION_CATEGORIES.items():
        if abstention_category_counts.get(category, 0) != expected_count:
            errors.append(
                f"Abstention category {category} must contain exactly {expected_count} examples, "
                f"found {abstention_category_counts.get(category, 0)}."
            )

    if status_counts.get("approved", 0) < 50:
        warnings.append(
            "Held-out fixture is structurally valid but human approval is still pending for one or more rows."
        )

    return {
        "errors": errors,
        "warnings": warnings,
        "total": len(rows),
        "answerable": behavior_counts.get("answer", 0),
        "abstention": behavior_counts.get("abstain", 0),
        "counts_by_category": dict(sorted(category_counts.items())),
        "counts_by_difficulty": dict(sorted(difficulty_counts.items())),
        "counts_by_question_style": dict(sorted(style_counts.items())),
        "validation_status_counts": {status: status_counts.get(status, 0) for status in sorted(ALLOWED_STATUSES)},
        "answerable_category_counts": {category: answerable_category_counts.get(category, 0) for category in ANSWERABLE_CATEGORIES},
        "abstention_category_counts": {category: abstention_category_counts.get(category, 0) for category in sorted(ABSTENTION_CATEGORIES)},
    }


def print_validation_report(report: dict[str, Any]) -> None:
    print(f"Total count: {report['total']}")
    print(f"Answerable count: {report['answerable']}")
    print(f"Abstention count: {report['abstention']}")
    print("Counts by category:")
    for key, value in report["counts_by_category"].items():
        print(f"  {key}: {value}")
    print("Counts by difficulty:")
    for key, value in report["counts_by_difficulty"].items():
        print(f"  {key}: {value}")
    print("Counts by question style:")
    for key, value in report["counts_by_question_style"].items():
        print(f"  {key}: {value}")
    print("Validation status counts:")
    for key in ("approved", "pending", "rejected"):
        print(f"  {key}: {report['validation_status_counts'].get(key, 0)}")
    for warning in report.get("warnings", []):
        print(f"WARNING: {warning}")


def validate_or_raise(rows: list[dict[str, Any]], seed_chunks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    report = validate_heldout_rows(rows, seed_chunks)
    if report["errors"]:
        details = "\n".join(f"- {error}" for error in report["errors"])
        raise EvaluationError(f"Held-out validation failed:\n{details}")
    return report


def human_validation_blockers(rows: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for row in rows:
        row_id = str(row.get("id") or "<missing-id>")
        validation = row.get("validation") or {}
        status = validation.get("status")
        reviewers = validation.get("reviewed_by") or []
        reviewer_names = [str(name).strip() for name in reviewers if str(name).strip()]
        if status != "approved" or not reviewer_names:
            blockers.append(f"{row_id} (status={status!r}, reviewers={len(reviewer_names)})")
    return blockers


def enforce_human_validation_gate(rows: list[dict[str, Any]]) -> None:
    blockers = human_validation_blockers(rows)
    if blockers:
        shown = "\n".join(f"- {item}" for item in blockers)
        raise EvaluationError(
            "Final Capstone collection is blocked until all 50 held-out rows are approved "
            "and each has at least one non-empty reviewer name.\n"
            f"Rows still needing human validation:\n{shown}"
        )


def is_abstention(answer: str) -> bool:
    normalized = normalize_text(answer)
    return any(normalize_text(phrase) in normalized for phrase in INSUFFICIENT_PHRASES)


def chunk_ids_from(items: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for item in items or []:
        chunk_id = str(item.get("chunk_id") or "").strip()
        if chunk_id:
            ids.append(chunk_id)
    return ids


def references_from(citations: list[dict[str, Any]], retrieved_chunks: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for group in (citations or [], retrieved_chunks or []):
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            reference = str(item.get("reference") or "").strip()
            if reference:
                refs.append(reference)
    return refs


def compute_retrieval_hit(expected_behavior: str, expected_ids: list[str], retrieved_ids: list[str]) -> bool | None:
    if expected_behavior != "answer":
        return None
    return bool(set(expected_ids) & set(retrieved_ids))


def compute_reference_hit(
    expected_behavior: str,
    expected_references: list[str],
    citations: list[dict[str, Any]],
    retrieved_chunks: list[dict[str, Any]],
) -> bool | None:
    if expected_behavior != "answer":
        return None
    actual_references = references_from(citations, retrieved_chunks)
    return any(
        expected == actual or expected in actual
        for expected in expected_references
        for actual in actual_references
    )


def compute_citation_validity(
    citations: list[dict[str, Any]],
    retrieved_chunks: list[dict[str, Any]],
    output_is_abstention: bool,
    error_detail: str,
) -> bool | None:
    if output_is_abstention or error_detail:
        return None
    cited_ids = chunk_ids_from(citations)
    retrieved_ids = set(chunk_ids_from(retrieved_chunks))
    if not cited_ids:
        return False
    return all(chunk_id in retrieved_ids for chunk_id in cited_ids)


def compute_review_key(record: dict[str, Any]) -> str:
    key_payload = {
        "question_id": record.get("question_id"),
        "system_name": record.get("system_name"),
        "normalized_answer": normalize_answer(str(record.get("answer") or "")),
        "citation_chunk_ids": chunk_ids_from(record.get("citations") or []),
        "retrieved_chunk_ids": list(record.get("retrieved_chunk_ids") or []),
    }
    encoded = json.dumps(key_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def make_result_record(
    example: dict[str, Any],
    *,
    system_name: str,
    run_id: str,
    seed: int | str | None,
    answer: str,
    confidence: float | None,
    citations: list[dict[str, Any]],
    retrieved_chunks: list[dict[str, Any]],
    latency_ms: float,
    http_status: int | None,
    error_detail: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retrieved_ids = chunk_ids_from(retrieved_chunks)
    output_is_abstention = is_abstention(answer)
    record: dict[str, Any] = {
        "question_id": example["id"],
        "question": example["question"],
        "expected_behavior": example["expected_behavior"],
        "gold_answer": example.get("gold_answer"),
        "required_points": list(example.get("required_points") or []),
        "expected_chunk_ids": list(example.get("expected_chunk_ids") or []),
        "expected_references": list(example.get("expected_references") or []),
        "metadata": dict(example.get("metadata") or {}),
        "system_name": system_name,
        "seed": seed,
        "run_id": run_id,
        "answer": answer,
        "confidence": confidence,
        "citations": citations,
        "retrieved_chunks": retrieved_chunks,
        "retrieved_chunk_ids": retrieved_ids,
        "latency_ms": round(float(latency_ms), 2),
        "http_status": http_status,
        "error_detail": error_detail,
        "output_is_abstention": output_is_abstention,
    }
    record["automated_retrieval_hit"] = compute_retrieval_hit(
        record["expected_behavior"],
        record["expected_chunk_ids"],
        retrieved_ids,
    )
    record["automated_reference_hit"] = compute_reference_hit(
        record["expected_behavior"],
        record["expected_references"],
        citations,
        retrieved_chunks,
    )
    record["automated_citation_valid"] = compute_citation_validity(
        citations,
        retrieved_chunks,
        output_is_abstention,
        error_detail,
    )
    if extra:
        record.update(extra)
    record["review_key"] = compute_review_key(record)
    return record


def sanitize_chunk(row: dict[str, Any]) -> dict[str, Any]:
    return {prop: row.get(prop) for prop in BASELINE_PROPERTIES}


def run_bm25_query(client: Any, question: str, weaviate_class: str = WEAVIATE_CLASS) -> dict[str, Any]:
    result = (
        client.query.get(weaviate_class, BASELINE_PROPERTIES)
        .with_bm25(query=question, properties=BASELINE_SEARCH_PROPERTIES)
        .with_limit(1)
        .do()
    )
    rows = result.get("data", {}).get("Get", {}).get(weaviate_class, [])
    if not rows:
        raise EvaluationError("baseline_no_result")
    if not isinstance(rows, list) or not isinstance(rows[0], dict):
        raise EvaluationError("baseline_invalid_payload")
    chunk = sanitize_chunk(rows[0])
    if not str(chunk.get("chunk_id") or "").strip() or not str(chunk.get("text") or "").strip():
        raise EvaluationError("baseline_invalid_chunk")
    return chunk


def collect_baseline(
    rows: list[dict[str, Any]],
    *,
    weaviate_url: str,
    weaviate_class: str = WEAVIATE_CLASS,
) -> list[dict[str, Any]]:
    import weaviate

    client = weaviate.Client(url=weaviate_url)
    records: list[dict[str, Any]] = []
    for example in rows:
        started = time.perf_counter()
        answer = ""
        citations: list[dict[str, Any]] = []
        retrieved_chunks: list[dict[str, Any]] = []
        error_detail = ""
        try:
            chunk = run_bm25_query(client, example["question"], weaviate_class)
            answer = f"{BASELINE_TEMPLATE}\n{chunk['text']}"
            citations = [
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "source_name": chunk.get("source_name"),
                    "reference": chunk.get("reference"),
                    "topic": chunk.get("topic"),
                    "source_page": chunk.get("source_page"),
                }
            ]
            retrieved_chunks = [chunk]
        except Exception as exc:
            error_detail = f"{type(exc).__name__}: {exc}"
        latency_ms = (time.perf_counter() - started) * 1000
        records.append(
            make_result_record(
                example,
                system_name="bm25_top1_baseline",
                run_id="baseline",
                seed="deterministic",
                answer=answer,
                confidence=None,
                citations=citations,
                retrieved_chunks=retrieved_chunks,
                latency_ms=latency_ms,
                http_status=None,
                error_detail=error_detail,
                extra={"weaviate_url": weaviate_url, "baseline": "bm25_top1_template"},
            )
        )
    return records


def seed_local_randomness(seed: int) -> list[str]:
    notes = ["random"]
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
        notes.append("numpy")
    except Exception:
        notes.append("numpy_unavailable")

    try:
        import torch

        torch.manual_seed(seed)
        notes.append("torch")
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            notes.append("torch_cuda")
    except Exception:
        notes.append("torch_unavailable")
    return notes


def call_rag_api(api_url: str, question: str, timeout: float) -> tuple[dict[str, Any], int | None, float, str]:
    import httpx

    url = f"{api_url.rstrip('/')}/rag/answer"
    started = time.perf_counter()
    try:
        response = httpx.post(url, json={"question": question, "k": 5}, timeout=timeout)
        latency_ms = (time.perf_counter() - started) * 1000
        status = response.status_code
        try:
            payload = response.json()
        except ValueError as exc:
            return {}, status, latency_ms, f"invalid_json_response: {exc}"
        if status >= 400:
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            return {}, status, latency_ms, f"HTTP {status}: {detail}"
        if not isinstance(payload, dict):
            return {}, status, latency_ms, "invalid_response_payload"
        return payload, status, latency_ms, ""
    except httpx.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {}, None, latency_ms, f"{type(exc).__name__}: {exc}"


def collect_system_run(
    rows: list[dict[str, Any]],
    *,
    api_url: str,
    timeout: float,
    seed: int,
) -> list[dict[str, Any]]:
    seeded_libraries = seed_local_randomness(seed)
    seed_note = (
        "The evaluator seeds locally controllable randomness. The remote xAI request path "
        "currently does not accept a seed through this integration. The API must run with "
        "LLM_TEMPERATURE=0 to minimize generation variance."
    )
    records: list[dict[str, Any]] = []
    for example in rows:
        payload, status, latency_ms, error_detail = call_rag_api(api_url, example["question"], timeout)
        answer = str(payload.get("answer") or "") if payload else ""
        confidence_raw = payload.get("confidence") if payload else None
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else None
        except (TypeError, ValueError):
            confidence = None
        citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
        retrieved_chunks = (
            payload.get("retrieved_chunks")
            if isinstance(payload.get("retrieved_chunks"), list)
            else []
        )
        records.append(
            make_result_record(
                example,
                system_name="rag_full_system",
                run_id=f"system_seed_{seed}",
                seed=seed,
                answer=answer,
                confidence=confidence,
                citations=citations,
                retrieved_chunks=retrieved_chunks,
                latency_ms=latency_ms,
                http_status=status,
                error_detail=error_detail,
                extra={
                    "api_url": api_url,
                    "seed_control": {
                        "local_seed": seed,
                        "seeded_libraries": seeded_libraries,
                        "note": seed_note,
                    },
                },
            )
        )
    return records


def create_timestamped_run_dir(output_dir: str | Path) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    base_name = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    candidate = root / base_name
    suffix = 1
    while candidate.exists():
        candidate = root / f"{base_name}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=False, exist_ok=False)
    return candidate


def csv_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def run_id_sort_key(run_id: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"system_seed_(\d+)", run_id)
    if match:
        return ("system_seed", int(match.group(1)), run_id)
    if run_id == "baseline":
        return ("baseline", -1, run_id)
    return (run_id, 0, run_id)


def full_evidence_from_chunk(
    chunk: dict[str, Any],
    seed_chunks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    chunk_id = str(chunk.get("chunk_id") or "").strip()
    seed_chunk = seed_chunks.get(chunk_id)
    if seed_chunk:
        return {
            "chunk_id": chunk_id,
            "reference": seed_chunk.get("reference"),
            "topic": seed_chunk.get("topic"),
            "text": seed_chunk.get("text"),
        }
    return {
        "chunk_id": chunk_id,
        "reference": chunk.get("reference"),
        "topic": chunk.get("topic"),
        "text": chunk.get("text") or chunk.get("text_preview"),
    }


def review_evidence(
    record: dict[str, Any],
    seed_chunks: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for chunk in record.get("retrieved_chunks") or []:
        if isinstance(chunk, dict):
            evidence.append(full_evidence_from_chunk(chunk, seed_chunks))
    return evidence


def generate_human_review_csv(run_dir: str | Path, records: list[dict[str, Any]]) -> Path:
    seed_chunks = load_seed_chunks(DEFAULT_SEED_CHUNKS)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in sorted(records, key=lambda item: (item.get("question_id", ""), item.get("system_name", ""), item.get("run_id", ""))):
        groups[record["review_key"]].append(record)

    fieldnames = [
        "review_key",
        "question_id",
        "system_name",
        "occurrences",
        "question",
        "expected_behavior",
        "gold_answer",
        "required_points",
        "expected_references",
        "answer",
        "returned_citations",
        "retrieved_evidence",
        "automated_retrieval_hit",
        "automated_citation_valid",
        "legal_correct",
        "evidence_supported",
        "citation_relevant",
        "material_hallucination",
        "abstention_correct",
        "reviewer",
        "review_notes",
    ]
    rows: list[dict[str, str]] = []
    for review_key, grouped in sorted(groups.items()):
        first = grouped[0]
        occurrences = sorted({str(item.get("run_id") or "") for item in grouped}, key=run_id_sort_key)
        rows.append(
            {
                "review_key": review_key,
                "question_id": str(first.get("question_id") or ""),
                "system_name": str(first.get("system_name") or ""),
                "occurrences": "|".join(occurrences),
                "question": str(first.get("question") or ""),
                "expected_behavior": str(first.get("expected_behavior") or ""),
                "gold_answer": "" if first.get("gold_answer") is None else str(first.get("gold_answer")),
                "required_points": csv_json(first.get("required_points") or []),
                "expected_references": csv_json(first.get("expected_references") or []),
                "answer": str(first.get("answer") or ""),
                "returned_citations": csv_json(first.get("citations") or []),
                "retrieved_evidence": csv_json(review_evidence(first, seed_chunks)),
                "automated_retrieval_hit": bool_to_cell(first.get("automated_retrieval_hit")),
                "automated_citation_valid": bool_to_cell(first.get("automated_citation_valid")),
                "legal_correct": "",
                "evidence_supported": "",
                "citation_relevant": "",
                "material_hallucination": "",
                "abstention_correct": "",
                "reviewer": "",
                "review_notes": "",
            }
        )

    target = Path(run_dir) / "human_review.csv"
    temp = target.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(target)
    return target


def collect_command(args: argparse.Namespace) -> int:
    if len(args.seeds) < 3:
        raise EvaluationError("Capstone collection requires at least three full-system seeds.")

    rows = load_jsonl(args.heldout)
    seed_chunks = load_seed_chunks(DEFAULT_SEED_CHUNKS)
    validate_or_raise(rows, seed_chunks)
    enforce_human_validation_gate(rows)

    run_dir = create_timestamped_run_dir(args.output_dir)
    print(f"Writing Capstone results to: {run_dir}")
    print(
        "Seed-control note: local random, numpy, and torch seeds are set when available; "
        "the remote xAI generation endpoint is not seed-controlled through this integration; "
        "run the API with LLM_TEMPERATURE=0."
    )

    baseline_records = collect_baseline(rows, weaviate_url=args.weaviate_url)
    write_jsonl_atomic(run_dir / "baseline.jsonl", baseline_records)

    all_records = list(baseline_records)
    for seed in args.seeds:
        records = collect_system_run(rows, api_url=args.api_url, timeout=args.timeout, seed=seed)
        write_jsonl_atomic(run_dir / f"system_seed_{seed}.jsonl", records)
        all_records.extend(records)

    review_path = generate_human_review_csv(run_dir, all_records)
    print(f"Human-review CSV: {review_path}")
    return 0


def read_review_csv(path: str | Path) -> dict[str, dict[str, str]]:
    source = Path(path)
    if not source.exists():
        raise EvaluationError(f"Missing human review CSV: {source}")
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    reviews: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []
    for row in rows:
        review_key = (row.get("review_key") or "").strip()
        if not review_key:
            continue
        if review_key in reviews:
            duplicates.append(review_key)
        reviews[review_key] = row
    if duplicates:
        raise EvaluationError(f"Duplicate review_key rows in human_review.csv: {', '.join(sorted(duplicates))}")
    return reviews


def validate_human_review(records: list[dict[str, Any]], reviews: dict[str, dict[str, str]]) -> None:
    incomplete: list[str] = []
    by_key: dict[str, dict[str, Any]] = {}
    for record in records:
        by_key.setdefault(record["review_key"], record)

    for review_key, record in sorted(by_key.items()):
        row = reviews.get(review_key)
        if row is None:
            incomplete.append(f"{review_key} ({record['question_id']}): missing review row")
            continue
        reviewer = (row.get("reviewer") or "").strip()
        if not reviewer:
            incomplete.append(f"{review_key} ({record['question_id']}): reviewer is required")
            continue
        if record.get("expected_behavior") == "answer":
            for field in ("legal_correct", "evidence_supported", "citation_relevant", "material_hallucination"):
                if (row.get(field) or "").strip() not in {"0", "1"}:
                    incomplete.append(f"{review_key} ({record['question_id']}): {field} must be 0 or 1")
        elif record.get("expected_behavior") == "abstain":
            if (row.get("abstention_correct") or "").strip() not in {"0", "1"}:
                incomplete.append(f"{review_key} ({record['question_id']}): abstention_correct must be 0 or 1")
            if is_substantive_response(record):
                for field in ("evidence_supported", "citation_relevant", "material_hallucination"):
                    if (row.get(field) or "").strip() not in {"0", "1"}:
                        incomplete.append(
                            f"{review_key} ({record['question_id']}): {field} must be 0 or 1 "
                            "when an expected-abstention question receives a substantive answer"
                        )

    if incomplete:
        shown = "\n".join(f"- {item}" for item in incomplete[:100])
        if len(incomplete) > 100:
            shown += f"\n- ... {len(incomplete) - 100} more incomplete review items"
        raise EvaluationError(f"Human review is incomplete or invalid:\n{shown}")


def grounded_answer_correct(record: dict[str, Any], review: dict[str, str]) -> bool:
    return (
        cell_to_bool(review, "legal_correct") is True
        and cell_to_bool(review, "evidence_supported") is True
        and cell_to_bool(review, "citation_relevant") is True
        and cell_to_bool(review, "material_hallucination") is False
        and record.get("automated_citation_valid") is True
    )


def abstention_correct(review: dict[str, str]) -> bool:
    return cell_to_bool(review, "abstention_correct") is True


def occurrence_success(record: dict[str, Any], review: dict[str, str]) -> bool:
    if record.get("expected_behavior") == "answer":
        return grounded_answer_correct(record, review)
    return abstention_correct(review)


def is_substantive_response(record: dict[str, Any]) -> bool:
    return (
        not record.get("output_is_abstention")
        and not record.get("error_detail")
        and bool(str(record.get("answer") or "").strip())
    )


def reliability_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(item.get("latency_ms") or 0.0) for item in records]
    errors = [item for item in records if item.get("error_detail")]
    return {
        "request_count": len(records),
        "api_error_count": len(errors),
        "api_error_rate": rate(len(errors), len(records)),
        "average_latency_ms": mean(latencies),
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
    }


def compute_run_metrics(records: list[dict[str, Any]], reviews: dict[str, dict[str, str]], *, baseline: bool) -> dict[str, Any]:
    answerable = [record for record in records if record.get("expected_behavior") == "answer"]
    abstentions = [record for record in records if record.get("expected_behavior") == "abstain"]
    grounded_count = sum(1 for record in answerable if grounded_answer_correct(record, reviews[record["review_key"]]))

    retrieval_values = [record.get("automated_retrieval_hit") for record in answerable if isinstance(record.get("automated_retrieval_hit"), bool)]
    reference_values = [record.get("automated_reference_hit") for record in answerable if isinstance(record.get("automated_reference_hit"), bool)]
    citation_values = [
        record.get("automated_citation_valid")
        for record in records
        if record.get("output_is_abstention") is False and isinstance(record.get("automated_citation_valid"), bool)
    ]
    substantive_records = [record for record in records if is_substantive_response(record)]
    evidence_supported = sum(
        1
        for record in substantive_records
        if cell_to_bool(reviews[record["review_key"]], "evidence_supported") is True
    )
    abstention_pass = sum(1 for record in abstentions if abstention_correct(reviews[record["review_key"]]))

    metrics: dict[str, Any] = {
        "system_name": records[0].get("system_name") if records else "",
        "run_id": records[0].get("run_id") if records else "",
        "seed": records[0].get("seed") if records else None,
        "answerable_denominator": len(answerable),
        "grounded_answer_correct_count": grounded_count,
        "grounded_answer_correctness": rate(grounded_count, len(answerable)),
        "reference_hit_count": sum(1 for value in reference_values if value is True),
        "reference_hit_denominator": len(reference_values),
        "reference_hit_rate": rate(sum(1 for value in reference_values if value is True), len(reference_values)),
        "citation_valid_count": sum(1 for value in citation_values if value is True),
        "citation_valid_denominator": len(citation_values),
        "citation_validity_rate": rate(sum(1 for value in citation_values if value is True), len(citation_values)),
        "evidence_supported_count": evidence_supported,
        "evidence_supported_denominator": len(substantive_records),
        "human_evidence_supported_grounding_rate": rate(evidence_supported, len(substantive_records)),
        "abstention_correct_count": abstention_pass,
        "abstention_denominator": len(abstentions),
        "abstention_accuracy": rate(abstention_pass, len(abstentions)),
        "reliability": reliability_metrics(records),
    }
    retrieval_count = sum(1 for value in retrieval_values if value is True)
    if baseline:
        metrics["hit_at_1_count"] = retrieval_count
        metrics["hit_at_1_denominator"] = len(retrieval_values)
        metrics["hit_at_1"] = rate(retrieval_count, len(retrieval_values))
    else:
        metrics["retrieval_hit_count"] = retrieval_count
        metrics["retrieval_hit_denominator"] = len(retrieval_values)
        metrics["retrieval_hit_rate_at_5"] = rate(retrieval_count, len(retrieval_values))
    return metrics


def latest_run_dir(results_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    root = Path(results_dir)
    if not root.exists():
        raise EvaluationError(f"No results directory exists at {root}.")
    candidates = sorted([path for path in root.iterdir() if path.is_dir()])
    if not candidates:
        raise EvaluationError(f"No timestamped run directories found under {root}.")
    return candidates[-1]


def load_run_directory(run_dir: str | Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    root = Path(run_dir)
    baseline_path = root / "baseline.jsonl"
    if not baseline_path.exists():
        raise EvaluationError(f"Missing baseline results: {baseline_path}")
    baseline_records = load_jsonl(baseline_path)
    system_paths = sorted(root.glob("system_seed_*.jsonl"))
    if len(system_paths) < 3:
        raise EvaluationError(f"Expected at least three system_seed_*.jsonl files in {root}, found {len(system_paths)}.")
    system_runs = {path.stem: load_jsonl(path) for path in system_paths}
    return baseline_records, system_runs


def group_error_rates(
    system_runs: dict[str, list[dict[str, Any]]],
    reviews: dict[str, dict[str, str]],
    dimension: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "errors": 0})
    for records in system_runs.values():
        for record in records:
            value = str((record.get("metadata") or {}).get(dimension) or "unknown")
            grouped[value]["total"] += 1
            if not occurrence_success(record, reviews[record["review_key"]]):
                grouped[value]["errors"] += 1
    return {
        key: {
            "total": counts["total"],
            "errors": counts["errors"],
            "error_rate": rate(counts["errors"], counts["total"]),
        }
        for key, counts in sorted(grouped.items())
    }


def classify_failure_reason(record: dict[str, Any], review: dict[str, str]) -> str:
    if record.get("error_detail"):
        return "API/generation error"
    if record.get("expected_behavior") == "abstain":
        if not record.get("output_is_abstention"):
            return "Failure to abstain"
        return "Incorrect abstention"
    if record.get("output_is_abstention"):
        return "Incorrect abstention"
    if record.get("automated_retrieval_hit") is False:
        return "Retrieval miss"
    if record.get("automated_citation_valid") is False or cell_to_bool(review, "citation_relevant") is False:
        return "Wrong or irrelevant citation"
    if cell_to_bool(review, "material_hallucination") is True or cell_to_bool(review, "evidence_supported") is False:
        return "Unsupported claim"
    if cell_to_bool(review, "legal_correct") is False:
        return "Missing required legal point"
    return "Grounded Answer Correctness failure"


def select_failure_cases(
    system_runs: dict[str, list[dict[str, Any]]],
    reviews: dict[str, dict[str, str]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for run_id, records in sorted(system_runs.items()):
        for record in sorted(records, key=lambda item: item.get("question_id", "")):
            review = reviews[record["review_key"]]
            if occurrence_success(record, review):
                continue
            reason = classify_failure_reason(record, review)
            failures.append(
                {
                    "question_id": record.get("question_id"),
                    "run_id": run_id,
                    "system_name": record.get("system_name"),
                    "question": record.get("question"),
                    "expected_behavior": record.get("expected_behavior"),
                    "category": (record.get("metadata") or {}).get("category"),
                    "question_style": (record.get("metadata") or {}).get("question_style"),
                    "difficulty": (record.get("metadata") or {}).get("difficulty"),
                    "failure_reason": reason,
                    "answer": record.get("answer"),
                    "expected_references": record.get("expected_references") or [],
                    "retrieved_chunk_ids": record.get("retrieved_chunk_ids") or [],
                    "citation_chunk_ids": chunk_ids_from(record.get("citations") or []),
                    "automated_retrieval_hit": record.get("automated_retrieval_hit"),
                    "automated_citation_valid": record.get("automated_citation_valid"),
                    "review_notes": (review.get("review_notes") or "").strip(),
                }
            )

    selected: list[dict[str, Any]] = []
    seen_reasons: set[str] = set()
    for failure in failures:
        if failure["failure_reason"] in seen_reasons:
            continue
        selected.append(failure)
        seen_reasons.add(failure["failure_reason"])
        if len(selected) == limit:
            return selected
    for failure in failures:
        if failure in selected:
            continue
        selected.append(failure)
        if len(selected) == limit:
            break
    return selected


def dataset_counts(records: list[dict[str, Any]]) -> dict[str, Any]:
    categories = Counter((record.get("metadata") or {}).get("category") for record in records)
    difficulty = Counter((record.get("metadata") or {}).get("difficulty") for record in records)
    styles = Counter((record.get("metadata") or {}).get("question_style") for record in records)
    behavior = Counter(record.get("expected_behavior") for record in records)
    return {
        "total": len(records),
        "answerable": behavior.get("answer", 0),
        "abstention": behavior.get("abstain", 0),
        "by_category": dict(sorted(categories.items())),
        "by_difficulty": dict(sorted(difficulty.items())),
        "by_question_style": dict(sorted(styles.items())),
    }


def build_targets(full_mean: dict[str, Any]) -> dict[str, dict[str, Any]]:
    target_specs = {
        "grounded_answer_correctness": 0.75,
        "retrieval_hit_rate_at_5": 0.80,
        "abstention_accuracy": 0.90,
    }
    targets: dict[str, dict[str, Any]] = {}
    for key, target in target_specs.items():
        value = full_mean.get(key, {}).get("mean")
        targets[key] = {
            "target": target,
            "value": value,
            "passed": None if value is None else value >= target,
        }
    return targets


def metric_mean_std(per_run: dict[str, dict[str, Any]], key: str) -> dict[str, float | None]:
    values = [metrics.get(key) for metrics in per_run.values() if isinstance(metrics.get(key), (int, float))]
    if not values:
        return {"mean": None, "population_std": None}
    float_values = [float(value) for value in values]
    return {"mean": mean(float_values), "population_std": population_std(float_values)}


def aggregate_run(
    run_dir: str | Path | None = None,
    *,
    next_hypothesis: str | None = None,
    report_dir: str | Path = DEFAULT_REPORT_DIR,
) -> dict[str, Any]:
    selected_run_dir = Path(run_dir) if run_dir else latest_run_dir()
    baseline_records, system_runs = load_run_directory(selected_run_dir)
    all_records = list(baseline_records)
    for records in system_runs.values():
        all_records.extend(records)

    reviews = read_review_csv(selected_run_dir / "human_review.csv")
    validate_human_review(all_records, reviews)

    baseline_metrics = compute_run_metrics(baseline_records, reviews, baseline=True)
    full_metrics = {
        run_id: compute_run_metrics(records, reviews, baseline=False)
        for run_id, records in sorted(system_runs.items())
    }
    full_mean_std = {
        "grounded_answer_correctness": metric_mean_std(full_metrics, "grounded_answer_correctness"),
        "retrieval_hit_rate_at_5": metric_mean_std(full_metrics, "retrieval_hit_rate_at_5"),
        "abstention_accuracy": metric_mean_std(full_metrics, "abstention_accuracy"),
        "reference_hit_rate": metric_mean_std(full_metrics, "reference_hit_rate"),
        "citation_validity_rate": metric_mean_std(full_metrics, "citation_validity_rate"),
    }
    breakdowns = {
        "category": group_error_rates(system_runs, reviews, "category"),
        "question_style": group_error_rates(system_runs, reviews, "question_style"),
        "difficulty": group_error_rates(system_runs, reviews, "difficulty"),
    }
    failure_cases = select_failure_cases(system_runs, reviews, limit=5)
    summary = {
        "dataset_counts": dataset_counts(baseline_records),
        "validation_methodology": {
            "heldout_rows": "All held-out questions, gold answers, required points, references, and chunks must be approved by human reviewers before collect can run.",
            "model_outputs": "All unique outputs are manually scored with a binary rubric in human_review.csv before aggregate can run.",
            "primary_metric": "Grounded Answer Correctness is calculated only from completed human-review rubric fields and automated citation validity.",
            "no_llm_judge": True,
        },
        "baseline_metrics": baseline_metrics,
        "per_seed_full_system_metrics": full_metrics,
        "full_system_mean_and_population_std": full_mean_std,
        "target_pass_fail": build_targets(full_mean_std),
        "breakdowns": breakdowns,
        "failure_cases": failure_cases,
        "limitations": [
            "The evaluator seeds locally controllable randomness, but the remote xAI request path currently does not accept a seed through this integration.",
            "The API must be run with LLM_TEMPERATURE=0 for final collection; this is a run precondition verified outside the evaluator.",
            "The system is an informational Jordanian employment-law explainer and not legal advice.",
            "Human legal correctness and evidence support judgments are binary and depend on reviewer completion quality.",
        ],
        "reproducibility_metadata": {
            "run_dir": str(selected_run_dir),
            "aggregated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "raw_files": ["baseline.jsonl"] + [f"{run_id}.jsonl" for run_id in sorted(system_runs)],
            "full_system_run_ids": sorted(system_runs),
            "population_standard_deviation": True,
            "baseline": "Deterministic BM25-only Top-1 retrieval with fixed template answer.",
            "temperature": "LLM_TEMPERATURE=0 is required for the evaluated API run.",
        },
        "next_iteration_hypothesis": next_hypothesis
        if next_hypothesis
        else "TODO: Add a specific evidence-based next-iteration hypothesis after reviewing the failure cases.",
    }
    write_json_atomic(selected_run_dir / "summary.json", summary)
    report_root = Path(report_dir)
    write_text_atomic(report_root / "EVALUATION_REPORT.md", render_evaluation_report(summary))
    write_text_atomic(report_root / "failure_cases.md", render_failure_cases(summary))
    return summary


def fmt_rate(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def fmt_float(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def fmt_ms(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1f} ms"


def target_label(item: dict[str, Any]) -> str:
    if item.get("passed") is True:
        return "PASS"
    if item.get("passed") is False:
        return "FAIL"
    return "n/a"


def render_metrics_table(summary: dict[str, Any]) -> str:
    lines = [
        "| Run | Primary GAC | Retrieval | Abstention Accuracy | Reference Hit | Citation Validity | Avg Latency | API Error Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    baseline = summary["baseline_metrics"]
    lines.append(
        "| BM25 Top-1 baseline | "
        f"{fmt_rate(baseline.get('grounded_answer_correctness'))} | "
        f"Hit@1 {fmt_rate(baseline.get('hit_at_1'))} | "
        f"{fmt_rate(baseline.get('abstention_accuracy'))} | "
        f"{fmt_rate(baseline.get('reference_hit_rate'))} | "
        f"{fmt_rate(baseline.get('citation_validity_rate'))} | "
        f"{fmt_ms(baseline.get('reliability', {}).get('average_latency_ms'))} | "
        f"{fmt_rate(baseline.get('reliability', {}).get('api_error_rate'))} |"
    )
    for run_id, metrics in summary["per_seed_full_system_metrics"].items():
        lines.append(
            f"| {run_id} | "
            f"{fmt_rate(metrics.get('grounded_answer_correctness'))} | "
            f"Hit Rate@5 {fmt_rate(metrics.get('retrieval_hit_rate_at_5'))} | "
            f"{fmt_rate(metrics.get('abstention_accuracy'))} | "
            f"{fmt_rate(metrics.get('reference_hit_rate'))} | "
            f"{fmt_rate(metrics.get('citation_validity_rate'))} | "
            f"{fmt_ms(metrics.get('reliability', {}).get('average_latency_ms'))} | "
            f"{fmt_rate(metrics.get('reliability', {}).get('api_error_rate'))} |"
        )
    mean_std = summary["full_system_mean_and_population_std"]
    lines.append(
        "| Full-system mean +/- population std | "
        f"{fmt_rate(mean_std['grounded_answer_correctness']['mean'])} +/- {fmt_rate(mean_std['grounded_answer_correctness']['population_std'])} | "
        f"Hit Rate@5 {fmt_rate(mean_std['retrieval_hit_rate_at_5']['mean'])} +/- {fmt_rate(mean_std['retrieval_hit_rate_at_5']['population_std'])} | "
        f"{fmt_rate(mean_std['abstention_accuracy']['mean'])} +/- {fmt_rate(mean_std['abstention_accuracy']['population_std'])} | "
        f"{fmt_rate(mean_std['reference_hit_rate']['mean'])} +/- {fmt_rate(mean_std['reference_hit_rate']['population_std'])} | "
        f"{fmt_rate(mean_std['citation_validity_rate']['mean'])} +/- {fmt_rate(mean_std['citation_validity_rate']['population_std'])} | "
        "n/a | n/a |"
    )
    return "\n".join(lines)


def render_breakdown_table(items: dict[str, dict[str, Any]]) -> str:
    lines = ["| Group | Total occurrences | Errors | Error rate |", "| --- | ---: | ---: | ---: |"]
    for group, data in items.items():
        lines.append(
            f"| {group} | {data.get('total', 0)} | {data.get('errors', 0)} | {fmt_rate(data.get('error_rate'))} |"
        )
    return "\n".join(lines)


def render_failure_case_list(failure_cases: list[dict[str, Any]]) -> str:
    if not failure_cases:
        return "No failed full-system examples were available after completed review."
    lines: list[str] = []
    for index, case in enumerate(failure_cases, start=1):
        notes = case.get("review_notes") or "No reviewer note provided."
        lines.extend(
            [
                f"{index}. `{case.get('question_id')}` / `{case.get('run_id')}` - {case.get('failure_reason')}",
                f"   Question: {case.get('question')}",
                f"   Category/style/difficulty: {case.get('category')} / {case.get('question_style')} / {case.get('difficulty')}",
                f"   Retrieved chunk IDs: {', '.join(case.get('retrieved_chunk_ids') or []) or 'none'}",
                f"   Citation chunk IDs: {', '.join(case.get('citation_chunk_ids') or []) or 'none'}",
                f"   Reviewer notes: {notes}",
            ]
        )
    return "\n".join(lines)


def render_evaluation_report(summary: dict[str, Any]) -> str:
    counts = summary["dataset_counts"]
    targets = summary["target_pass_fail"]
    mean_std = summary["full_system_mean_and_population_std"]
    baseline = summary["baseline_metrics"]
    full_runs = summary["per_seed_full_system_metrics"]
    first_run = next(iter(full_runs.values())) if full_runs else {}
    reliability = first_run.get("reliability", {})
    report = f"""# Lawz AI JO Capstone RAG Evaluation

## 1. Executive Summary

This report evaluates the Jordanian employment-law RAG system on a frozen 50-question held-out set. The primary metric is Grounded Answer Correctness on the 40 answerable questions. The full-system mean is {fmt_rate(mean_std['grounded_answer_correctness']['mean'])} +/- {fmt_rate(mean_std['grounded_answer_correctness']['population_std'])} population standard deviation across the full-system runs.

## 2. System Under Evaluation

The system under evaluation is the deployed `POST /rag/answer` API. It retrieves Jordanian labor-law evidence, generates an Arabic informational answer, and returns backend-generated citations, confidence, retrieved chunk previews, and a legal disclaimer. The system is an informational legal explainer, not legal advice.

## 3. Held-Out Dataset

The dataset contains {counts['total']} Arabic questions: {counts['answerable']} answerable and {counts['abstention']} abstention cases. The questions and gold answers were manually validated by the team before final collection.

## 4. Human-Validation Method

The held-out questions, gold answers, required points, expected chunks, and references must be approved by human reviewers before collection. Model outputs were manually scored with a binary rubric in `human_review.csv`; no LLM judge, word-overlap score, translation step, or automatic legal grader is used for the primary metric.

## 5. Primary Metric

Grounded Answer Correctness passes only when legal correctness, evidence support, and citation relevance are all marked `1`, material hallucination is marked `0`, and automated citation validity is true. It is calculated on the 40 answerable questions.

## 6. Secondary Metrics

Secondary metrics include Retrieval Hit Rate@5 for the full system, baseline Hit@1, reference hit rate, citation validity on non-abstaining responses, Grounding Rate over substantive responses, abstention accuracy, API error rate, and latency.

## 7. BM25 Top-1 Baseline

The baseline is deterministic. It uses Weaviate BM25 only, retrieves the Top-1 chunk, and answers with the fixed template `وفقًا للمصدر القانوني المسترجع:` followed by the full retrieved chunk text. Baseline Grounded Answer Correctness is {fmt_rate(baseline.get('grounded_answer_correctness'))}; baseline Hit@1 is {fmt_rate(baseline.get('hit_at_1'))}.

## 8. Three-Run Reproducibility Method

The full system contains stochastic generation. Temperature was set to zero for evaluation as a required run precondition. The evaluator seeded locally controllable randomness before each run, but the remote xAI generation endpoint was not seed-controlled through the current integration.

## 9. Results Table

{render_metrics_table(summary)}

## 10. Results by Category

{render_breakdown_table(summary['breakdowns']['category'])}

## 11. Results by Question Style

{render_breakdown_table(summary['breakdowns']['question_style'])}

## 12. Results by Difficulty

{render_breakdown_table(summary['breakdowns']['difficulty'])}

## 13. Five Representative Failure Cases

{render_failure_case_list(summary['failure_cases'])}

## 14. Error Analysis

The error grids above report full-system failure rates across category, question style, and difficulty. Failure reasons were selected from reviewed failed occurrences and prioritize distinct causes such as retrieval miss, unsupported claim, wrong or irrelevant citation, incorrect abstention, failure to abstain, and API/generation error.

## 15. Latency and Reliability

For the first full-system run shown, request count was {reliability.get('request_count', 0)}, API error rate was {fmt_rate(reliability.get('api_error_rate'))}, average latency was {fmt_ms(reliability.get('average_latency_ms'))}, p50 latency was {fmt_ms(reliability.get('p50_latency_ms'))}, and p95 latency was {fmt_ms(reliability.get('p95_latency_ms'))}. Per-run values are available in `summary.json`.

## 16. Limitations

{chr(10).join(f'- {item}' for item in summary['limitations'])}

## 17. One Next-Iteration Hypothesis

{summary['next_iteration_hypothesis']}

## 18. Conclusion Against the Three Targets

| Target | Threshold | Value | Result |
| --- | ---: | ---: | --- |
| Grounded Answer Correctness | >= {fmt_rate(targets['grounded_answer_correctness']['target'])} | {fmt_rate(targets['grounded_answer_correctness']['value'])} | {target_label(targets['grounded_answer_correctness'])} |
| Retrieval Hit Rate@5 | >= {fmt_rate(targets['retrieval_hit_rate_at_5']['target'])} | {fmt_rate(targets['retrieval_hit_rate_at_5']['value'])} | {target_label(targets['retrieval_hit_rate_at_5'])} |
| Abstention Accuracy | >= {fmt_rate(targets['abstention_accuracy']['target'])} | {fmt_rate(targets['abstention_accuracy']['value'])} | {target_label(targets['abstention_accuracy'])} |
"""
    return report


def render_failure_cases(summary: dict[str, Any]) -> str:
    return "# Capstone Failure Cases\n\n" + render_failure_case_list(summary["failure_cases"]) + "\n"


def aggregate_command(args: argparse.Namespace) -> int:
    summary = aggregate_run(args.run_dir, next_hypothesis=args.next_hypothesis)
    print(f"Aggregated run directory: {summary['reproducibility_metadata']['run_dir']}")
    print("Generated summary.json, eval/EVALUATION_REPORT.md, and eval/failure_cases.md")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    rows = load_jsonl(args.heldout)
    seed_chunks = load_seed_chunks(args.seed_chunks)
    report = validate_heldout_rows(rows, seed_chunks)
    print_validation_report(report)
    if report["errors"]:
        for error in report["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lawz AI JO Capstone RAG evaluation harness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate the held-out JSONL fixture.")
    validate_parser.add_argument("--heldout", default=str(DEFAULT_HELDOUT))
    validate_parser.add_argument("--seed-chunks", default=str(DEFAULT_SEED_CHUNKS))
    validate_parser.set_defaults(func=validate_command)

    collect_parser = subparsers.add_parser("collect", help="Collect baseline and full-system evaluation runs.")
    collect_parser.add_argument("--api-url", default=DEFAULT_API_URL)
    collect_parser.add_argument("--weaviate-url", default=DEFAULT_WEAVIATE_URL)
    collect_parser.add_argument("--timeout", type=float, default=300)
    collect_parser.add_argument("--heldout", default=str(DEFAULT_HELDOUT))
    collect_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    collect_parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    collect_parser.set_defaults(func=collect_command)

    aggregate_parser = subparsers.add_parser("aggregate", help="Aggregate reviewed raw results and generate reports.")
    aggregate_parser.add_argument("--run-dir", default=None)
    aggregate_parser.add_argument("--next-hypothesis", default=None)
    aggregate_parser.set_defaults(func=aggregate_command)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return int(args.func(args))
    except EvaluationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
