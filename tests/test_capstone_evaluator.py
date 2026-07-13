import csv
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_EVAL_PATH = REPO_ROOT / "eval" / "run_eval.py"

spec = importlib.util.spec_from_file_location("capstone_run_eval", RUN_EVAL_PATH)
capstone = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(capstone)


def load_rows():
    return capstone.load_jsonl(REPO_ROOT / "eval" / "heldout.jsonl")


def load_seed_chunks():
    return capstone.load_seed_chunks(REPO_ROOT / "api" / "seed_chunks.json")


def test_jsonl_loading_and_heldout_schema_validation():
    rows = load_rows()
    seed_chunks = load_seed_chunks()

    report = capstone.validate_heldout_rows(rows, seed_chunks)

    assert report["errors"] == []
    assert report["total"] == 50
    assert report["answerable"] == 40
    assert report["abstention"] == 10
    assert report["answerable_category_counts"] == {
        "contracts_probation_flexible_work": 8,
        "termination_notice_unfair_dismissal": 8,
        "wages_deductions_overtime": 8,
        "leave_hours_weekly_rest": 8,
        "worker_protection_safety_social_security": 8,
    }
    assert [row["id"] for row in rows] == [f"lawz-{index:03d}" for index in range(1, 51)]


def test_expected_chunks_and_references_exist_in_seed_chunks():
    rows = load_rows()
    seed_chunks = load_seed_chunks()

    for row in rows:
        for chunk_id in row["expected_chunk_ids"]:
            assert chunk_id in seed_chunks
        seed_refs = {seed_chunks[chunk_id]["reference"] for chunk_id in row["expected_chunk_ids"]}
        for reference in row["expected_references"]:
            assert reference in seed_refs


def test_corrected_heldout_rows_have_fair_required_points():
    rows = {row["id"]: row for row in load_rows()}

    assert rows["lawz-002"]["required_points"] == [
        "عدم كتابة العقد لا يمنع العامل من إثبات حقوقه.",
        "يجوز للعامل إثبات حقوقه بجميع طرق الإثبات القانونية.",
    ]
    assert rows["lawz-004"]["required_points"] == [
        "مدة التجربة لا تزيد على ثلاثة أشهر.",
        "يجوز لصاحب العمل إنهاء الاستخدام خلال التجربة دون إشعار أو مكافأة.",
    ]
    assert rows["lawz-006"]["required_points"] == [
        "تحويل العقد غير المرن إلى عمل مرن يتم بالاتفاق بين الطرفين.",
        "لا يجوز التحويل إذا كان ينتقص من حقوق العامل المنصوص عليها في القانون.",
    ]
    assert rows["lawz-007"]["required_points"] == [
        "صاحب العمل يرد خلال مدة لا تتجاوز عشرة أيام عمل من تاريخ تقديم الطلب.",
        "يجوز التحويل بين العمل المرن وغير المرن بعد مضي مدة لا تقل عن ثلاثة أشهر من تاريخ التحويل.",
    ]
    assert rows["lawz-009"]["required_points"] == [
        "الإشعار يجب أن يكون خطيًا.",
        "مدة الإشعار شهر واحد على الأقل قبل إنهاء العقد غير محدد المدة.",
    ]
    assert rows["lawz-014"]["required_points"] == [
        "العامل يستوفي الحقوق والمزايا المنصوص عليها في العقد.",
        "يستحق الأجور حتى انتهاء المدة المتبقية من العقد.",
        "لا تنطبق هذه القاعدة إذا كان الإنهاء فصلًا بموجب المادة 28.",
    ]
    assert rows["lawz-019"]["required_points"] == [
        "الأجر وبدل العمل الإضافي يدفعان خلال مدة لا تزيد على سبعة أيام من تاريخ الاستحقاق.",
        "توقيع العامل على كشف أو سجل أجور أو إيصال لا يسقط حقه في الزيادة المستحقة بموجب القانون أو النظام أو العقد.",
    ]
    assert rows["lawz-020"]["required_points"] == [
        "استرداد السلف التي قدمها صاحب العمل للعامل مسموح.",
        "كل قسط يسترد من السلفة لا يجوز أن يزيد على 10% من الأجر.",
    ]
    assert rows["lawz-021"]["required_points"] == [
        "اللجنة الثلاثية هي التي تحدد الحد الأدنى للأجور.",
        "تشكل اللجنة من ممثلين عن الوزارة والعمال وأصحاب العمل.",
    ]
    assert rows["lawz-035"]["required_points"] == [
        "الالتزام يطبق على صاحب العمل الذي يستخدم عشرين عاملًا فأكثر.",
        "يجب إجراء تقييم للمخاطر المهنية في بيئة العمل.",
    ]
    assert rows["lawz-037"]["required_points"] == [
        "يشمل الحكم حوادث العمل والحوادث الوشيكة التي كان يمكن أن تؤدي إلى ضرر أو إصابة وفق نص المادة.",
        "يجب تبليغ الوزارة خلال 48 ساعة من تاريخ وقوع الحادث.",
    ]


def test_lawz_039_has_qualified_nationality_social_security_scope():
    row = {item["id"]: item for item in load_rows()}["lawz-039"]

    assert row["question"] == "هل كون العامل غير أردني يمنع شمولَه بالضمان الاجتماعي؟"
    assert row["expected_chunk_ids"] == ["official_social_security_law_2014_art_004"]
    assert row["expected_references"] == [
        "قانون الضمان الاجتماعي رقم 1 لسنة 2014 وتعديلاته حتى 16/4/2023، المادة 4"
    ]
    assert row["required_points"] == [
        "الجنسية غير الأردنية وحدها لا تمنع الشمول.",
        "يشترط إكمال سن السادسة عشرة ضمن الفئات المحددة.",
        "تشمل القاعدة العمال الخاضعين لقانون العمل.",
        "يظل الشمول خاضعًا لشروط انتظام العمل والاستثناءات القانونية.",
    ]


def test_duplicate_normalized_question_detection():
    rows = [dict(row) for row in load_rows()]
    rows[1]["question"] = rows[0]["question"]

    report = capstone.validate_heldout_rows(rows, load_seed_chunks())

    assert any("duplicate normalized question" in error for error in report["errors"])


def test_abstention_detection_recognizes_known_phrases():
    assert capstone.is_abstention("لا تكفي قاعدة المعرفة الحالية للإجابة بثقة.")
    assert capstone.is_abstention("السياق غير كاف للإجابة.")
    assert not capstone.is_abstention("الإجابة المختصرة: يستحق العامل أجره.")


def test_retrieval_hit_and_citation_validity():
    assert capstone.compute_retrieval_hit("answer", ["a", "b"], ["x", "b"]) is True
    assert capstone.compute_retrieval_hit("answer", ["a"], ["x"]) is False
    assert capstone.compute_retrieval_hit("abstain", [], ["x"]) is None

    citations = [{"chunk_id": "a"}, {"chunk_id": "b"}]
    retrieved = [{"chunk_id": "a"}, {"chunk_id": "b"}, {"chunk_id": "c"}]
    assert capstone.compute_citation_validity(citations, retrieved, False, "") is True
    assert capstone.compute_citation_validity([{"chunk_id": "z"}], retrieved, False, "") is False
    assert capstone.compute_citation_validity([], retrieved, False, "") is False
    assert capstone.compute_citation_validity(citations, retrieved, True, "") is None


def good_review(**overrides):
    row = {
        "legal_correct": "1",
        "evidence_supported": "1",
        "citation_relevant": "1",
        "material_hallucination": "0",
        "abstention_correct": "",
        "reviewer": "Reviewer One",
        "review_notes": "",
    }
    row.update(overrides)
    return row


def make_record(example, *, run_id="system_seed_42", answer="إجابة", retrieved_id=None, citation_id=None):
    retrieved_id = retrieved_id or (example["expected_chunk_ids"][0] if example["expected_chunk_ids"] else "none")
    citation_id = citation_id or retrieved_id
    citations = [] if example["expected_behavior"] == "abstain" else [{"chunk_id": citation_id, "reference": (example["expected_references"] or [""])[0]}]
    retrieved = [] if example["expected_behavior"] == "abstain" else [{"chunk_id": retrieved_id, "reference": (example["expected_references"] or [""])[0], "topic": "topic", "text_preview": "evidence"}]
    if example["expected_behavior"] == "abstain":
        answer = "لا تكفي قاعدة المعرفة الحالية للإجابة بثقة."
    return capstone.make_result_record(
        example,
        system_name="rag_full_system",
        run_id=run_id,
        seed=42,
        answer=answer,
        confidence=0.8,
        citations=citations,
        retrieved_chunks=retrieved,
        latency_ms=25.0,
        http_status=200,
        error_detail="",
    )


def test_human_review_validation_and_grounded_correctness_logic():
    example = load_rows()[0]
    record = make_record(example)
    reviews = {record["review_key"]: good_review()}

    capstone.validate_human_review([record], reviews)
    assert capstone.grounded_answer_correct(record, reviews[record["review_key"]]) is True

    bad = {record["review_key"]: good_review(material_hallucination="1")}
    assert capstone.grounded_answer_correct(record, bad[record["review_key"]]) is False

    incomplete = {record["review_key"]: good_review(legal_correct="", reviewer="")}
    with pytest.raises(capstone.EvaluationError):
        capstone.validate_human_review([record], incomplete)


def test_expected_abstention_substantive_answer_requires_evidence_review_fields():
    example = {row["id"]: row for row in load_rows()}["lawz-041"]
    record = capstone.make_result_record(
        example,
        system_name="rag_full_system",
        run_id="system_seed_42",
        seed=42,
        answer="يمكن فتح حساب بنكي من خلال البنك.",
        confidence=0.5,
        citations=[],
        retrieved_chunks=[],
        latency_ms=5,
        http_status=200,
        error_detail="",
    )

    incomplete = {
        record["review_key"]: {
            "abstention_correct": "0",
            "reviewer": "Reviewer One",
            "evidence_supported": "",
            "citation_relevant": "",
            "material_hallucination": "",
            "legal_correct": "",
        }
    }
    with pytest.raises(capstone.EvaluationError):
        capstone.validate_human_review([record], incomplete)

    complete = {
        record["review_key"]: {
            "abstention_correct": "0",
            "reviewer": "Reviewer One",
            "evidence_supported": "0",
            "citation_relevant": "0",
            "material_hallucination": "1",
            "legal_correct": "",
        }
    }
    capstone.validate_human_review([record], complete)


def test_deduplicates_identical_outputs_in_human_review_csv(tmp_path):
    example = load_rows()[0]
    first = make_record(example, run_id="system_seed_42", answer="نفس الإجابة")
    second = make_record(example, run_id="system_seed_1337", answer="نفس الإجابة")
    third = make_record(example, run_id="system_seed_2024", answer="إجابة مختلفة")

    review_path = capstone.generate_human_review_csv(tmp_path, [first, second, third])

    with review_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    occurrences = sorted(row["occurrences"] for row in rows)
    assert "system_seed_42|system_seed_1337" in occurrences
    assert "system_seed_2024" in occurrences


def test_human_review_csv_uses_full_seed_text_not_api_preview(tmp_path):
    example = load_rows()[0]
    seed_chunks = load_seed_chunks()
    chunk_id = example["expected_chunk_ids"][0]
    record = capstone.make_result_record(
        example,
        system_name="rag_full_system",
        run_id="system_seed_42",
        seed=42,
        answer="إجابة",
        confidence=0.8,
        citations=[{"chunk_id": chunk_id, "reference": example["expected_references"][0]}],
        retrieved_chunks=[
            {
                "chunk_id": chunk_id,
                "reference": "api reference",
                "topic": "api topic",
                "text_preview": "TRUNCATED API PREVIEW",
            }
        ],
        latency_ms=10,
        http_status=200,
        error_detail="",
    )

    review_path = capstone.generate_human_review_csv(tmp_path, [record])

    with review_path.open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    evidence = json.loads(row["retrieved_evidence"])
    assert evidence[0]["chunk_id"] == chunk_id
    assert evidence[0]["text"] == seed_chunks[chunk_id]["text"]
    assert evidence[0]["text"] != "TRUNCATED API PREVIEW"


def test_mean_population_std_and_percentiles():
    values = [0.5, 0.75, 1.0]
    assert capstone.mean(values) == 0.75
    assert math.isclose(capstone.population_std(values), 0.2041241452, rel_tol=1e-6)
    assert capstone.percentile([100, 200, 300, 400], 50) == 250
    assert capstone.percentile([100, 200, 300, 400], 95) == 385


def test_error_grid_grouping():
    examples = load_rows()
    good_record = make_record(examples[0])
    bad_record = make_record(examples[1], answer="إجابة ناقصة")
    reviews = {
        good_record["review_key"]: good_review(),
        bad_record["review_key"]: good_review(legal_correct="0"),
    }

    grid = capstone.group_error_rates({"system_seed_42": [good_record, bad_record]}, reviews, "category")

    category = examples[0]["metadata"]["category"]
    assert grid[category]["total"] == 2
    assert grid[category]["errors"] == 1
    assert grid[category]["error_rate"] == 0.5


def test_grounding_rate_counts_substantive_abstention_failures_and_excludes_true_abstentions():
    rows = {row["id"]: row for row in load_rows()}
    answerable = make_record(rows["lawz-001"], answer="إجابة مدعومة")
    failed_abstention = capstone.make_result_record(
        rows["lawz-041"],
        system_name="rag_full_system",
        run_id="system_seed_42",
        seed=42,
        answer="إجابة غير لازمة عن فتح الحساب.",
        confidence=0.5,
        citations=[],
        retrieved_chunks=[],
        latency_ms=5,
        http_status=200,
        error_detail="",
    )
    true_abstention = capstone.make_result_record(
        rows["lawz-042"],
        system_name="rag_full_system",
        run_id="system_seed_42",
        seed=42,
        answer="لا تكفي قاعدة المعرفة الحالية للإجابة بثقة.",
        confidence=0.0,
        citations=[],
        retrieved_chunks=[],
        latency_ms=5,
        http_status=200,
        error_detail="",
    )
    reviews = {
        answerable["review_key"]: good_review(),
        failed_abstention["review_key"]: {
            "abstention_correct": "0",
            "reviewer": "Reviewer One",
            "evidence_supported": "1",
            "citation_relevant": "0",
            "material_hallucination": "1",
            "legal_correct": "",
        },
        true_abstention["review_key"]: {
            "abstention_correct": "1",
            "reviewer": "Reviewer One",
            "evidence_supported": "",
            "citation_relevant": "",
            "material_hallucination": "",
            "legal_correct": "",
        },
    }

    metrics = capstone.compute_run_metrics(
        [answerable, failed_abstention, true_abstention],
        reviews,
        baseline=False,
    )

    assert metrics["evidence_supported_count"] == 2
    assert metrics["evidence_supported_denominator"] == 2
    assert metrics["human_evidence_supported_grounding_rate"] == 1.0


def test_retrieval_metric_is_serialized_as_hit_rate_at_5():
    example = load_rows()[0]
    record = make_record(example)
    reviews = {record["review_key"]: good_review()}

    metrics = capstone.compute_run_metrics([record], reviews, baseline=False)

    assert metrics["retrieval_hit_rate_at_5"] == 1.0
    assert "retrieval_hit_rate_recall_at_5" not in metrics


class FakeQueryBuilder:
    def __init__(self, payload):
        self.payload = payload

    def get(self, *_args, **_kwargs):
        return self

    def with_bm25(self, *_args, **_kwargs):
        return self

    def with_limit(self, *_args, **_kwargs):
        return self

    def do(self):
        return self.payload


def test_bm25_baseline_query_uses_mocked_weaviate_client():
    payload = {
        "data": {
            "Get": {
                "LegalChunk": [
                    {
                        "chunk_id": "chunk-a",
                        "source_name": "source",
                        "reference": "ref",
                        "topic": "topic",
                        "text": "النص القانوني",
                        "source_page": None,
                        "source_type": "official",
                        "jurisdiction": "Jordan",
                    }
                ]
            }
        }
    }
    fake_client = SimpleNamespace(query=FakeQueryBuilder(payload))

    chunk = capstone.run_bm25_query(fake_client, "سؤال")

    assert chunk["chunk_id"] == "chunk-a"
    assert chunk["text"] == "النص القانوني"


def test_http_system_call_uses_mocked_httpx(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"answer": "إجابة", "confidence": 0.7, "citations": [], "retrieved_chunks": []}

    fake_httpx = SimpleNamespace(
        HTTPError=Exception,
        post=lambda *args, **kwargs: FakeResponse(),
    )
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    payload, status, latency, error = capstone.call_rag_api("http://example.test", "سؤال", 1)

    assert payload["answer"] == "إجابة"
    assert status == 200
    assert latency >= 0
    assert error == ""


def write_completed_review_csv(run_dir, records):
    review_path = capstone.generate_human_review_csv(run_dir, records)
    with review_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = handle.seek(0) or list(rows[0].keys())

    by_key = {record["review_key"]: record for record in records}
    completed = []
    for row in rows:
        record = by_key[row["review_key"]]
        row["reviewer"] = "Reviewer One"
        if record["expected_behavior"] == "answer":
            row["legal_correct"] = "1"
            row["evidence_supported"] = "1"
            row["citation_relevant"] = "1"
            row["material_hallucination"] = "0"
        else:
            row["abstention_correct"] = "1"
            if capstone.is_substantive_response(record):
                row["evidence_supported"] = "0"
                row["citation_relevant"] = "0"
                row["material_hallucination"] = "1"
        if record["question_id"] == "lawz-001" and record["run_id"] == "system_seed_42":
            row["legal_correct"] = "0"
            row["review_notes"] = "Missed an essential contract point."
        if record["question_id"] == "lawz-041" and record["run_id"] == "system_seed_42":
            row["abstention_correct"] = "0"
            row["review_notes"] = "Answered an out-of-scope banking question."
        completed.append(row)

    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(completed[0].keys()))
        writer.writeheader()
        writer.writerows(completed)


def build_fake_run_dir(tmp_path):
    rows = load_rows()
    run_dir = tmp_path / "2026-07-13T120000Z"
    run_dir.mkdir()

    baseline = [make_record(example, run_id="baseline", answer="baseline") for example in rows]
    for record in baseline:
        record["system_name"] = "bm25_top1_baseline"
        record["seed"] = "deterministic"
        record["review_key"] = capstone.compute_review_key(record)
    capstone.write_jsonl_atomic(run_dir / "baseline.jsonl", baseline)

    all_records = list(baseline)
    for seed in (42, 1337, 2024):
        records = []
        for example in rows:
            if seed == 42 and example["id"] == "lawz-001":
                record = make_record(example, run_id=f"system_seed_{seed}", answer="إجابة ناقصة", retrieved_id="wrong", citation_id="wrong")
            elif seed == 42 and example["id"] == "lawz-041":
                record = capstone.make_result_record(
                    example,
                    system_name="rag_full_system",
                    run_id=f"system_seed_{seed}",
                    seed=seed,
                    answer="يمكنك فتح الحساب من البنك.",
                    confidence=0.5,
                    citations=[],
                    retrieved_chunks=[],
                    latency_ms=30,
                    http_status=200,
                    error_detail="",
                )
            else:
                record = make_record(example, run_id=f"system_seed_{seed}", answer="إجابة صحيحة")
            records.append(record)
        capstone.write_jsonl_atomic(run_dir / f"system_seed_{seed}.jsonl", records)
        all_records.extend(records)

    write_completed_review_csv(run_dir, all_records)
    return run_dir


def test_report_generation_with_temporary_fake_results(tmp_path):
    run_dir = build_fake_run_dir(tmp_path)

    summary = capstone.aggregate_run(
        run_dir,
        next_hypothesis="Improve citation filtering for answerable contract questions.",
        report_dir=tmp_path,
    )

    assert (run_dir / "summary.json").exists()
    assert (tmp_path / "EVALUATION_REPORT.md").exists()
    assert (tmp_path / "failure_cases.md").exists()
    assert summary["dataset_counts"]["total"] == 50
    assert "category" in summary["breakdowns"]
    assert summary["full_system_mean_and_population_std"]["grounded_answer_correctness"]["mean"] is not None
    assert "retrieval_hit_rate_at_5" in summary["full_system_mean_and_population_std"]
    assert "retrieval_hit_rate_recall_at_5" not in summary["full_system_mean_and_population_std"]
    assert "Retrieval Hit Rate@5" in (tmp_path / "EVALUATION_REPORT.md").read_text(encoding="utf-8")
    assert "Recall@5" not in (tmp_path / "EVALUATION_REPORT.md").read_text(encoding="utf-8")
