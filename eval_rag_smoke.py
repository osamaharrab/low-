from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any


INSUFFICIENT_ANSWER = "لا تكفي قاعدة المعرفة الحالية للإجابة بثقة"


def load_fixture(path: str | Path) -> list[dict[str, Any]]:
    fixture_path = Path(path)
    text = fixture_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
    else:
        data = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(data, list):
        raise ValueError(f"{fixture_path} must contain a JSON array or JSONL rows.")
    return data


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def is_abstention(answer: str) -> bool:
    return INSUFFICIENT_ANSWER in (answer or "")


def _response_ids(response: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for item in response.get("citations") or []:
        if item.get("chunk_id"):
            ids.add(str(item["chunk_id"]))
    for item in response.get("retrieved_chunks") or []:
        if item.get("chunk_id"):
            ids.add(str(item["chunk_id"]))
    return ids


def _response_references(response: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for group in ("citations", "retrieved_chunks"):
        for item in response.get(group) or []:
            if item.get("reference"):
                refs.append(str(item["reference"]))
    return refs


def score_response(item: dict[str, Any], response: dict[str, Any], latency_ms: float, error: str | None = None) -> dict[str, Any]:
    answer = str(response.get("answer") or "") if response else ""
    citations = response.get("citations") or [] if response else []
    retrieved_chunks = response.get("retrieved_chunks") or [] if response else []
    expected_chunk_ids = set(item.get("expected_chunk_ids") or [])
    expected_references = list(item.get("expected_references") or [])
    if item.get("expected_reference_contains"):
        expected_references.append(str(item["expected_reference_contains"]))

    response_ids = _response_ids(response or {})
    response_refs = _response_references(response or {})
    retrieval_hit = None
    if expected_chunk_ids:
        retrieval_hit = bool(expected_chunk_ids & response_ids)

    reference_hit = None
    if expected_references:
        reference_hit = any(expected in ref for expected in expected_references for ref in response_refs)

    failure_reasons: list[str] = []
    if error:
        failure_reasons.append(error)
    if not answer.strip():
        failure_reasons.append("missing_answer")
    if expected_chunk_ids and not retrieval_hit:
        failure_reasons.append("retrieval_miss")
    if expected_references and not reference_hit:
        failure_reasons.append("reference_miss")

    return {
        "question": item.get("question", ""),
        "category": item.get("category"),
        "answer_exists": bool(answer.strip()),
        "abstained": is_abstention(answer),
        "citation_present": bool(citations),
        "retrieval_hit": retrieval_hit,
        "reference_hit": reference_hit,
        "latency_ms": round(latency_ms, 2),
        "citations": citations,
        "retrieved_chunk_ids": [chunk.get("chunk_id") for chunk in retrieved_chunks],
        "failure_reasons": failure_reasons,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    latencies = [float(item.get("latency_ms") or 0.0) for item in results]
    summary: dict[str, Any] = {
        "total": total,
        "answered_count": sum(1 for item in results if item.get("answer_exists") and not item.get("abstained")),
        "abstention_count": sum(1 for item in results if item.get("abstained")),
        "citation_present_rate": round(sum(1 for item in results if item.get("citation_present")) / total, 3) if total else 0.0,
        "average_latency_ms": round(sum(latencies) / total, 2) if total else 0.0,
        "p95_latency_ms": round(percentile(latencies, 95), 2),
        "failures": [
            {
                "question": item.get("question"),
                "failure_reasons": item.get("failure_reasons", []),
            }
            for item in results
            if item.get("failure_reasons")
        ],
        "per_question": results,
    }

    retrieval_values = [item["retrieval_hit"] for item in results if item.get("retrieval_hit") is not None]
    if retrieval_values:
        summary["retrieval_hit_rate"] = round(sum(1 for value in retrieval_values if value) / len(retrieval_values), 3)

    reference_values = [item["reference_hit"] for item in results if item.get("reference_hit") is not None]
    if reference_values:
        summary["reference_hit_rate"] = round(sum(1 for value in reference_values if value) / len(reference_values), 3)

    return summary


def call_api(api_url: str, question: str, timeout: float) -> tuple[dict[str, Any], float, str | None]:
    import httpx

    started = time.perf_counter()
    try:
        response = httpx.post(
            f"{api_url.rstrip('/')}/rag/answer",
            json={"question": question, "k": 5},
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        response.raise_for_status()
        return response.json(), latency_ms, None
    except (httpx.HTTPError, ValueError) as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {}, latency_ms, str(exc)


def run_evaluation(api_url: str, fixture: str, timeout: float, output: str) -> dict[str, Any]:
    rows = load_fixture(fixture)
    results = []
    for item in rows:
        question = item.get("question")
        if not question:
            results.append(score_response(item, {}, 0.0, "missing_question"))
            continue
        response, latency_ms, error = call_api(api_url, question, timeout)
        results.append(score_response(item, response, latency_ms, error))

    report = summarize_results(results)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Lawz AI JO RAG smoke evaluation.")
    parser.add_argument("--api-url", default="http://localhost:8001")
    parser.add_argument("--fixture", default="data/rag_smoke.json")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", default="outputs/rag_smoke_results.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_evaluation(args.api_url, args.fixture, args.timeout, args.output)
    summary = {key: value for key, value in report.items() if key != "per_question"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
