import json

from eval_kg import load_fixture, normalize_cypher, percentile, score_response, summarize_results, run_evaluation


def test_cypher_whitespace_normalization():
    assert normalize_cypher("MATCH   (n)\n\nRETURN   n") == "MATCH (n) RETURN n"


def test_keyword_uppercasing_preserves_string_literals():
    normalized = normalize_cypher("match (n) where n.text = 'match return' return n")

    assert normalized == "MATCH (n) WHERE n.text = 'match return' RETURN n"


def test_trailing_semicolon_removal():
    assert normalize_cypher("MATCH (n) RETURN n;") == "MATCH (n) RETURN n"


def test_exact_match_scoring():
    item = {
        "question": "ما المواد؟",
        "gold_cypher": "match (n:Article) return n",
    }
    response = {
        "generated_cypher": "MATCH   (n:Article)\nRETURN n;",
        "row_count": 1,
    }

    result = score_response(item, response, latency_ms=12.5)
    summary = summarize_results([result])

    assert result["exact_match"] is True
    assert summary["exact_matches"] == 1
    assert summary["exact_match_accuracy"] == 1.0


def test_empty_fixture_behavior(tmp_path):
    fixture = tmp_path / "kg_questions.json"
    output = tmp_path / "kg_eval_results.json"
    fixture.write_text("[]", encoding="utf-8")

    rows = load_fixture(fixture)
    report = run_evaluation("http://localhost:8001", str(fixture), 1, str(output))

    assert rows == []
    assert report["total"] == 0
    assert report["exact_match_accuracy"] == 0.0
    assert report["valid_cypher_rate"] == 0.0
    assert report["execution_success_rate"] == 0.0
    assert json.loads(output.read_text(encoding="utf-8"))["per_question"] == []


def test_p95_behavior_on_small_latency_list():
    assert round(percentile([10, 20, 30, 40], 95), 2) == 38.5
