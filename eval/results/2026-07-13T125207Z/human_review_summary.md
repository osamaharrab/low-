# Human Review Evaluation Summary

Metrics are weighted by the number of values in the `occurrences` column.

| System | Weighted outputs | Legal correctness | Evidence supported | Citation relevance | Abstention accuracy | Hallucination rate | Overall correctness |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bm25_top1_baseline` | 50 | 40.00% | 100.00% | 50.00% | 0.00% | 0.00% | 32.00% |
| `rag_full_system` | 150 | 40.00% | 65.00% | 12.50% | 100.00% | 0.00% | 52.00% |

## RAG improvement over baseline

| Metric | Baseline | RAG | Difference |
|---|---:|---:|---:|
| `legal_correct_rate` | 40.00% | 40.00% | +0.00 percentage points |
| `evidence_supported_rate` | 100.00% | 65.00% | -35.00 percentage points |
| `citation_relevant_rate` | 50.00% | 12.50% | -37.50 percentage points |
| `material_hallucination_rate` | 0.00% | 0.00% | +0.00 percentage points |
| `abstention_accuracy` | 0.00% | 100.00% | +100.00 percentage points |
| `overall_correctness` | 32.00% | 52.00% | +20.00 percentage points |
