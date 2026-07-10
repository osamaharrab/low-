from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path
from typing import Any


CYPHER_PHRASE_KEYWORDS = (
    "OPTIONAL MATCH",
    "ORDER BY",
    "LOAD CSV",
    "DETACH DELETE",
)
CYPHER_SINGLE_KEYWORDS = (
    "MATCH",
    "WHERE",
    "RETURN",
    "WITH",
    "LIMIT",
    "UNION",
    "UNWIND",
    "AS",
    "AND",
    "OR",
    "NOT",
    "IN",
    "CONTAINS",
    "STARTS",
    "ENDS",
    "BY",
    "ORDER",
    "OPTIONAL",
)
FORBIDDEN_PATTERNS = (
    r"\bDETACH\s+DELETE\b",
    r"\bLOAD\s+CSV\b",
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bDELETE\b",
    r"\bSET\b",
    r"\bREMOVE\b",
    r"\bDROP\b",
    r"\bCALL\b",
    r"\bFOREACH\b",
    r"\bGRANT\b",
    r"\bDENY\b",
    r"\bREVOKE\b",
)
READ_ONLY_START_RE = re.compile(r"^(MATCH|OPTIONAL\s+MATCH|WHERE|RETURN|WITH|UNWIND)\b", flags=re.IGNORECASE)


def load_fixture(path: str | Path) -> list[dict[str, Any]]:
    fixture_path = Path(path)
    text = fixture_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"{fixture_path} must contain a JSON array.")
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


def _semicolon_positions_outside_strings(text: str) -> list[int]:
    positions: list[int] = []
    quote: str | None = None
    escaped = False
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == ";":
            positions.append(index)
    return positions


def remove_trailing_semicolon(cypher: str) -> str:
    text = (cypher or "").strip()
    positions = _semicolon_positions_outside_strings(text)
    if positions and not text[positions[-1] + 1 :].strip():
        return text[: positions[-1]].rstrip()
    return text


def _split_string_literals(text: str) -> list[tuple[bool, str]]:
    segments: list[tuple[bool, str]] = []
    buffer: list[str] = []
    quote: str | None = None
    escaped = False
    literal_start = False

    def flush(is_literal: bool) -> None:
        nonlocal buffer
        if buffer:
            segments.append((is_literal, "".join(buffer)))
            buffer = []

    for char in text:
        if quote:
            buffer.append(char)
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
                flush(True)
                literal_start = False
            continue

        if char in {"'", '"'}:
            flush(False)
            quote = char
            buffer.append(char)
            literal_start = True
            continue

        buffer.append(char)

    flush(bool(quote or literal_start))
    return segments


def _uppercase_keywords(segment: str) -> str:
    normalized = re.sub(r"\s+", " ", segment)
    for keyword in CYPHER_PHRASE_KEYWORDS:
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in keyword.split()) + r"\b"
        normalized = re.sub(pattern, keyword, normalized, flags=re.IGNORECASE)
    for keyword in CYPHER_SINGLE_KEYWORDS:
        normalized = re.sub(rf"\b{re.escape(keyword)}\b", keyword, normalized, flags=re.IGNORECASE)
    return normalized


def normalize_cypher(cypher: str) -> str:
    text = remove_trailing_semicolon(cypher)
    segments = _split_string_literals(text)
    normalized_parts = [
        segment if is_literal else _uppercase_keywords(segment)
        for is_literal, segment in segments
    ]
    return "".join(normalized_parts).strip()


def is_valid_cypher(cypher: str) -> bool:
    cleaned = remove_trailing_semicolon(cypher)
    if not cleaned or len(cleaned) > 4000 or "```" in cleaned:
        return False
    if _semicolon_positions_outside_strings(cleaned):
        return False

    non_literal = "".join(
        " " * len(segment) if is_literal else segment
        for is_literal, segment in _split_string_literals(cleaned)
    )
    normalized = re.sub(r"\s+", " ", non_literal).strip().upper()
    if not READ_ONLY_START_RE.match(normalized):
        return False
    if not re.search(r"\bRETURN\b", normalized):
        return False
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, normalized):
            return False
    return True


def call_api(api_url: str, question: str, timeout: float) -> tuple[dict[str, Any], float, str | None]:
    import httpx

    started = time.perf_counter()
    try:
        response = httpx.post(
            f"{api_url.rstrip('/')}/kg/query",
            json={"question": question},
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        response.raise_for_status()
        return response.json(), latency_ms, None
    except (httpx.HTTPError, ValueError) as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {}, latency_ms, str(exc)


def score_response(item: dict[str, Any], response: dict[str, Any], latency_ms: float, error: str | None = None) -> dict[str, Any]:
    gold_cypher = str(item.get("gold_cypher") or "")
    generated_cypher = str(response.get("generated_cypher") or "") if response else ""
    normalized_gold = normalize_cypher(gold_cypher)
    normalized_generated = normalize_cypher(generated_cypher)
    exact_match = bool(normalized_gold) and normalized_generated == normalized_gold
    valid_cypher = bool(generated_cypher.strip()) and is_valid_cypher(generated_cypher)
    execution_success = error is None and bool(response)

    failure_reasons: list[str] = []
    if error:
        failure_reasons.append(error)
    if not item.get("question"):
        failure_reasons.append("missing_question")
    if not normalized_gold:
        failure_reasons.append("missing_gold_cypher")
    if generated_cypher and not valid_cypher:
        failure_reasons.append("invalid_generated_cypher")
    if normalized_gold and not exact_match:
        failure_reasons.append("cypher_mismatch")

    return {
        "question": item.get("question", ""),
        "gold_cypher": gold_cypher,
        "generated_cypher": generated_cypher,
        "normalized_gold_cypher": normalized_gold,
        "normalized_generated_cypher": normalized_generated,
        "exact_match": exact_match,
        "valid_cypher": valid_cypher,
        "execution_success": execution_success,
        "row_count": response.get("row_count") if response else None,
        "latency_ms": round(latency_ms, 2),
        "failure_reasons": failure_reasons,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    latencies = [float(item.get("latency_ms") or 0.0) for item in results]
    exact_matches = sum(1 for item in results if item.get("exact_match"))
    valid_cypher_count = sum(1 for item in results if item.get("valid_cypher"))
    execution_success_count = sum(1 for item in results if item.get("execution_success"))

    return {
        "total": total,
        "exact_matches": exact_matches,
        "exact_match_accuracy": round(exact_matches / total, 3) if total else 0.0,
        "valid_cypher_count": valid_cypher_count,
        "valid_cypher_rate": round(valid_cypher_count / total, 3) if total else 0.0,
        "execution_success_count": execution_success_count,
        "execution_success_rate": round(execution_success_count / total, 3) if total else 0.0,
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
    }


def run_evaluation(api_url: str, fixture: str, timeout: float, output: str) -> dict[str, Any]:
    rows = load_fixture(fixture)
    results: list[dict[str, Any]] = []
    for item in rows:
        question = item.get("question")
        if not question:
            results.append(score_response(item, {}, 0.0, "missing_question"))
            continue
        response, latency_ms, error = call_api(api_url, question, timeout)
        results.append(score_response(item, response, latency_ms, error))

    summary = summarize_results(results)
    report = {**summary, "per_question": results}
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Lawz AI JO KG Text2Cypher evaluation.")
    parser.add_argument("--api-url", default="http://localhost:8001")
    parser.add_argument("--fixture", default="data/kg_questions.json")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", default="outputs/kg_eval_results.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_evaluation(args.api_url, args.fixture, args.timeout, args.output)
    summary = {key: value for key, value in report.items() if key != "per_question"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
