import json

from eval_rag_smoke import load_fixture, score_response, summarize_results


def test_load_fixture_supports_json_array(tmp_path):
    fixture = tmp_path / "rag_smoke.json"
    fixture.write_text(json.dumps([{"question": "سؤال؟"}], ensure_ascii=False), encoding="utf-8")

    rows = load_fixture(fixture)

    assert rows == [{"question": "سؤال؟"}]


def test_score_response_and_summary_on_fake_response():
    item = {
        "question": "هل يجوز إنهاء عقد العمل بدون إشعار؟",
        "expected_chunk_ids": ["chunk-a"],
        "expected_reference_contains": "المادة 23",
    }
    response = {
        "answer": "إجابة مختصرة",
        "citations": [
            {
                "chunk_id": "chunk-a",
                "reference": "قانون العمل الأردني، المادة 23",
            }
        ],
        "retrieved_chunks": [
            {
                "chunk_id": "chunk-b",
                "reference": "مرجع آخر",
            }
        ],
    }

    result = score_response(item, response, latency_ms=25.5)
    summary = summarize_results([result])

    assert result["answer_exists"] is True
    assert result["citation_present"] is True
    assert result["retrieval_hit"] is True
    assert result["reference_hit"] is True
    assert summary["total"] == 1
    assert summary["retrieval_hit_rate"] == 1.0
    assert summary["reference_hit_rate"] == 1.0
