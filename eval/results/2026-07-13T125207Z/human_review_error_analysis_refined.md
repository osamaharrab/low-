# Refined Human Review Error Analysis

The earlier broad generation-failure category has been separated into false abstention, empty generation, and unsupported generated answers.

| System | Failure category | Weighted failures |
|---|---|---:|
| `bm25_top1_baseline` | Retrieval/source mismatch | 20 |
| `bm25_top1_baseline` | Failed to abstain | 10 |
| `bm25_top1_baseline` | Incomplete/incorrect answer | 4 |
| `rag_full_system` | False abstention | 41 |
| `rag_full_system` | Citation selection issue | 40 |
| `rag_full_system` | Retrieval/source mismatch | 23 |
| `rag_full_system` | Incomplete/incorrect answer | 7 |
| `rag_full_system` | Empty/failed generation | 1 |
