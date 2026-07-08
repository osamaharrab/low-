# Lawz AI JO

Lawz AI JO is a focused Arabic RAG assistant for Jordanian labor-law questions. A user asks a legal-information question in Arabic, the API retrieves relevant Jordanian labor-law chunks from Weaviate, builds a grounded Arabic prompt, calls Ollama with `qwen3:4b`, and returns an Arabic answer with backend-generated citations, retrieved chunk previews, confidence, and a legal disclaimer.

## Scope

This project does:

- Answer Arabic Jordanian labor-law information questions using Retrieval-Augmented Generation.
- Retrieve legal chunks from Weaviate using sentence-transformers embeddings.
- Generate concise Arabic explanations with Ollama `qwen3:4b`.
- Expose FastAPI health, readiness, metrics, and RAG endpoints.
- Provide a simple Next.js UI and a smoke evaluation script.

This project does not do PDF uploads, DOCX parsing, contract review, legal risk scoring, knowledge graphs, paid APIs, or general legal chatbot behavior.

## Architecture

User → Web → FastAPI → Weaviate retrieval → Ollama `qwen3:4b` → answer/citations

## Stack

- Python 3.11
- FastAPI
- Weaviate
- sentence-transformers
- Ollama `qwen3:4b`
- Next.js
- Docker Compose
- Prometheus metrics

## Folder Structure

```text
api/
  main.py
  rag.py
  generator.py
  seed_weaviate.py
  seed_chunks.json
data/
  rag_smoke.json
tests/
web/
docker-compose.yml
eval_rag_smoke.py
requirements.txt
seed_weaviate.sh
```

## Environment Setup

```bash
cp .env.example .env
```

No secrets are required. Ollama runs on the host at `localhost:11434`, and the API container reaches it through `host.docker.internal`.

## Manual Run

Verify Ollama is installed and running:

```bash
ollama --version
ollama pull qwen3:4b
```

Start the local stack:

```bash
docker compose up -d --build
```

Seed Weaviate:

```bash
docker compose exec api ./seed_weaviate.sh
```

Check health:

```bash
curl http://localhost:8001/healthz
curl http://localhost:8001/readyz
```

Ask a RAG question:

```bash
curl -X POST http://localhost:8001/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"هل يجوز إنهاء عقد العمل بدون إشعار؟","k":5}'
```

Open the web UI:

```text
http://localhost:3001
```

Run the smoke evaluation:

```bash
python eval_rag_smoke.py
```

## Evaluation

`eval_rag_smoke.py` reads `data/rag_smoke.json`, calls `POST /rag/answer`, measures latency, checks whether an answer and citations are present, counts abstentions, and computes retrieval hit rate when expected chunk IDs are available. It writes a JSON report to `outputs/rag_smoke_results.json`.

The initial fixture contains 5 smoke questions. The current baseline is intended as a small capstone smoke benchmark, not a full legal QA benchmark.

## Monitoring

- `GET /metrics` exposes Prometheus metrics for request count, request latency, in-flight requests, RAG outcomes, retrieved chunks, and generation errors.
- `GET /healthz` returns basic API health.
- `GET /readyz` checks Weaviate and Ollama reachability.
- Every response includes `X-Request-ID`.
- Request logs are structured JSON lines with timestamp, request ID, method, path, status, and latency.

## Limitations

- This is not legal advice.
- The current corpus is limited to selected Jordanian labor-law chunks.
- Answers depend on retrieval quality.
- The LLM may summarize imperfectly.
- Users must verify important conclusions against official law and a qualified lawyer.

## Future Work

- Expand the evaluation set to 50+ hand-labeled questions.
- Improve retrieval with hybrid BM25+dense search.
- Add a dataset card.
- Add a public demo artifact.
- Consider optional contract upload later, outside this MVP scope.

## Capstone Fit

- Primary AI capability: Retrieval-Augmented Generation.
- AISPIRE components: M8 RAG/Weaviate, M10 FastAPI/Docker/Next.js, M11 monitoring/evaluation.
- Deployment: local Docker Compose.
- Evaluation: smoke benchmark with citation, abstention, latency, and retrieval/reference metrics.

## License

MIT
