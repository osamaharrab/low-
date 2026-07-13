# Multi-Seed Stability Summary

The BM25 baseline is deterministic and is reported as a single result. The RAG system was evaluated with seeds `42`, `1337`, and `2024`.

The reported standard deviation is the population standard deviation across the three seeds, matching the Module 12 formula.

**Primary metric:** human-reviewed overall correctness.

| Metric | Baseline | Seed 42 | Seed 1337 | Seed 2024 | RAG mean ± stddev |
|---|---:|---:|---:|---:|---:|
| Overall correctness (PRIMARY) | 32.00% | 52.00% | 50.00% | 54.00% | 52.00% ± 1.63% |
| Legal correctness | 40.00% | 40.00% | 37.50% | 42.50% | 40.00% ± 2.04% |
| Evidence supported | 100.00% | 65.00% | 65.00% | 65.00% | 65.00% ± 0.00% |
| Human citation relevance | 50.00% | 12.50% | 12.50% | 12.50% | 12.50% ± 0.00% |
| Human abstention accuracy | 0.00% | 100.00% | 100.00% | 100.00% | 100.00% ± 0.00% |
| Material hallucination rate | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% ± 0.00% |
| Automated retrieval hit | 45.00% | 70.00% | 70.00% | 70.00% | 70.00% ± 0.00% |
| Automated reference hit | 45.00% | 72.50% | 72.50% | 72.50% | 72.50% ± 0.00% |
| Automated citation validity | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% ± 0.00% |
| False abstention rate | 0.00% | 35.00% | 32.50% | 35.00% | 34.17% ± 1.18% |
| Request success rate | 100.00% | 100.00% | 98.00% | 100.00% | 99.33% ± 0.94% |
| Request error rate | 0.00% | 0.00% | 2.00% | 0.00% | 0.67% ± 0.94% |
| Timeout rate | 0.00% | 0.00% | 2.00% | 0.00% | 0.67% ± 0.94% |
| Average latency | 2.42 ms | 5657.96 ms | 6500.17 ms | 6135.66 ms | 6097.93 ± 344.87 ms |
| p95 latency | 3.06 ms | 7643.26 ms | 9111.99 ms | 8788.23 ms | 8514.49 ± 630.07 ms |
