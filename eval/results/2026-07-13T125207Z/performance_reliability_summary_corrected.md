# Corrected Performance and Reliability Summary

The BM25 baseline is local, so HTTP status is not applicable. Baseline success is based on completion without `error_detail`.

## Aggregate comparison

| System | Requests | Success rate | Error rate | 5xx rate | Timeout rate | Average latency (ms) | Median latency (ms) | p95 latency (ms) | Max latency (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bm25_top1_baseline` | 50 | 100.00% | 0.00% | N/A | 0.00% | 2.42 | 2.35 | 3.06 | 3.97 |
| `rag_full_system_aggregate` | 150 | 99.33% | 0.67% | 0.67% | 0.67% | 6097.93 | 6107.35 | 8788.23 | 30130.59 |

## Per-run RAG stability

| Run | Requests | Success rate | Error rate | Timeout rate | Average latency (ms) | p95 latency (ms) |
|---|---:|---:|---:|---:|---:|---:|
| `system_seed_42` | 50 | 100.00% | 0.00% | 0.00% | 5657.96 | 7643.26 |
| `system_seed_1337` | 50 | 98.00% | 2.00% | 2.00% | 6500.17 | 9111.99 |
| `system_seed_2024` | 50 | 100.00% | 0.00% | 0.00% | 6135.66 | 8788.23 |
