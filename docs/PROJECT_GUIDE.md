# Lawz AI JO Project Guide

This guide explains the Lawz AI JO capstone project in enough detail for teammates, reviewers, and future PDF export.

## 1. Project Overview

Lawz AI JO is a focused Arabic Retrieval-Augmented Generation (RAG) assistant for Jordanian labor-law information. It accepts an Arabic question, retrieves relevant legal chunks from Weaviate, builds a grounded Arabic prompt, calls a local Ollama `qwen3:4b` model, and returns an Arabic answer with backend-generated citations.

The project is intentionally small. It is not a broad legal chatbot. It demonstrates a clean RAG workflow with local Docker services, local generation, observability, and smoke evaluation.

## 2. Problem Statement

Jordanian labor-law information can be hard to search and summarize for non-specialists. The project provides a simple interface where a user can ask a labor-law information question in Arabic and receive a short grounded explanation with references to retrieved source chunks.

The answer is informational only. It is not a final legal opinion and does not replace official legal texts or a qualified lawyer.

## 3. Scope

The project does:

- Accept Arabic labor-law information questions.
- Embed the question with `intfloat/multilingual-e5-small`.
- Retrieve relevant legal chunks from Weaviate.
- Apply a simple lexical overlap rerank on top of vector retrieval.
- Build a grounded Arabic prompt from retrieved context.
- Call local Ollama with `qwen3:4b`.
- Return an Arabic answer, backend citations, retrieved chunk previews, confidence, and disclaimer.
- Expose health, readiness, metrics, and structured logs.
- Provide a simple Next.js web UI.
- Provide a smoke evaluation script.

## 4. Non-scope

The project does not include:

- PDF upload.
- DOCX parsing.
- Contract review.
- Risk scoring.
- Neo4j.
- Knowledge graph features.
- LangChain.
- Paid APIs.
- OpenAI or Groq API calls.
- Broad legal chatbot behavior.
- Production legal-advice workflows.

## 5. Architecture

```text
User
  -> Web UI on http://localhost:3001
  -> FastAPI on http://localhost:8001
  -> Weaviate on http://localhost:8081
  -> retrieved legal chunks
  -> Ollama qwen3:4b on http://localhost:11434
  -> Arabic answer with backend citations
```

Docker Compose runs Weaviate, the FastAPI API, and the web UI. Ollama does not run in Docker. It runs on the teammate's host machine, and the API container connects to it through:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

## 6. File-by-file Explanation

### `api/main.py`

Creates the FastAPI application. It defines:

- `GET /healthz` for basic API health.
- `GET /readyz` for Weaviate and Ollama readiness checks.
- `POST /rag/answer` for the main RAG answer endpoint.
- CORS settings for the web UI.
- Observability middleware and metrics setup.

The route catches Ollama generation errors and returns a clean service-unavailable response.

### `api/settings.py`

Defines environment-driven settings using Pydantic settings. Important values include Weaviate URL/class, embedding model, retrieval limits, Ollama URL/model, timeout, API URL, web URL, and CORS origin.

### `api/models.py`

Defines Pydantic request and response models:

- `RAGRequest`
- `Citation`
- `RetrievedChunk`
- `RAGResponse`
- `HealthResponse`
- `ReadyResponse`

These models keep the API response shape explicit and testable.

### `api/deps.py`

Small dependency module that exposes `get_settings` and `Settings` for FastAPI dependency injection.

### `api/rag.py`

Contains the core RAG flow:

1. Normalize and embed the user question.
2. Query Weaviate using a near-vector search.
3. Convert vector distance to an approximate score.
4. Rerank using a small lexical overlap bonus.
5. Build a grounded Arabic prompt from the top retrieved chunks.
6. Call the generator.
7. Clean the answer.
8. Build backend citations and retrieved chunk previews.

Citations are created by the backend from retrieved chunks. The LLM is not trusted to invent or format citations.

### `api/generator.py`

Calls Ollama through HTTP using `httpx`. It uses the `/api/chat` endpoint with:

- model: `qwen3:4b`
- temperature: `0.1`
- `stream: false`

It removes `<think>...</think>` blocks from model output and returns an abstention message if the output is empty.

### `api/observability.py`

Defines:

- Prometheus counters, histograms, and gauges.
- Request ID middleware.
- Structured JSON request logging.
- Metrics middleware.
- `/metrics` ASGI app mount.

Metric labels are bounded and do not include user questions or request IDs.

### `api/seed_weaviate.py`

Seeds Weaviate from `api/seed_chunks.json`. It:

1. Reads and validates seed chunks.
2. Connects to Weaviate.
3. Deletes the existing `LegalChunk` class if present.
4. Creates a schema with external vectors and cosine distance.
5. Embeds chunk text with `intfloat/multilingual-e5-small`.
6. Batch inserts chunks with vectors.
7. Prints a short summary.

Known successful seed summary:

```text
class: LegalChunk
chunks_loaded: 73
embedding_model: intfloat/multilingual-e5-small
first_chunk_id: official_labor_law_art_002_p01
last_chunk_id: betterwork_guide_page_067
```

### `api/seed_chunks.json`

JSON array containing the legal chunks used for Weaviate seeding. Each chunk includes:

- `chunk_id`
- `source_name`
- `reference`
- `topic`
- `text`
- `source_page`
- `source_type`
- `jurisdiction`
- `embedding_text`

The current seed file contains 73 legal chunks.

### `data/rag_smoke.json`

Small smoke evaluation fixture. It contains 5 Arabic test questions and expected topic/reference hints where available.

### `eval_rag_smoke.py`

Command-line smoke evaluation script. It calls the live API, measures latency, checks answer presence, citation presence, abstention count, retrieval hits when expected chunk IDs exist, and reference hits when expected reference text exists.

Default output:

```text
outputs/rag_smoke_results.json
```

### `docker-compose.yml`

Defines the local stack:

- `weaviate` on host port `8081`.
- `api` on host port `8001`.
- `web` on host port `3001`.

It also maps `host.docker.internal` so the API container can reach host Ollama.

### `api/Dockerfile`

Builds the Python API image. It installs CPU-only Torch first, then installs `requirements.txt`, copies the API package and seed script, and starts Uvicorn.

### `web/pages/index.js`

Simple Next.js page with:

- Project title.
- Arabic subtitle.
- Text area for questions.
- Ask button.
- Sample questions.
- Answer display.
- Citations display.
- Retrieved chunks display.
- Disclaimer display.

### `web/package.json`

Defines the web dependencies and scripts:

- `next`
- `react`
- `react-dom`
- `npm run dev`
- `npm run build`
- `npm run start`

### `seed_weaviate.sh`

Small helper script that runs:

```bash
python -m api.seed_weaviate
```

On Windows, teammates can run the Python module directly inside the API container instead:

```powershell
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

### `README.md`

Primary teammate-facing setup document. It is Windows-first and includes ports, prerequisites, setup commands, troubleshooting, evaluation, and GitHub safety notes.

## 7. Runtime Flow

### User Question

The user enters an Arabic labor-law information question in the web UI or sends it directly to:

```text
POST /rag/answer
```

Example:

```json
{
  "question": "هل يجوز إنهاء عقد العمل بدون إشعار؟",
  "k": 5
}
```

### Question Embedding

The API formats the question for the E5 embedding model:

```text
query: {question}
```

It embeds the question using `intfloat/multilingual-e5-small`.

### Weaviate Retrieval

The API queries the `LegalChunk` class in Weaviate using near-vector search. It asks for legal chunk fields plus vector distance metadata.

### Reranking

The API combines:

- Vector score from Weaviate distance.
- Small lexical overlap bonus from normalized Arabic question terms and chunk text/topic/reference.

This stays simple and avoids cross-encoders or additional ML models.

### Prompt Building

The API builds a grounded Arabic prompt from the top retrieved chunks. The prompt tells the model:

- Use only retrieved legal texts.
- Do not invent references.
- Do not provide final legal advice.
- Say clearly when context is insufficient.
- Do not output `<think>`.

### Ollama Generation

The API calls:

```text
http://host.docker.internal:11434/api/chat
```

with model:

```text
qwen3:4b
```

### Response With Backend Citations

The API returns:

- `answer`
- `citations`
- `confidence`
- `retrieved_chunks`
- `disclaimer`

Citations are created from retrieved chunks, not from the LLM output.

## 8. Models

### Embedding Model

```text
intfloat/multilingual-e5-small
```

This model supports multilingual retrieval and works well with E5 prefixes:

- `query:` for user questions.
- `passage:` for legal chunks.

### Generator

```text
Ollama qwen3:4b
```

This model runs locally through Ollama. It can be slow on typical laptops. In the successful local run, some answers took around 2-4 minutes.

## 9. Data

### Legal Chunks

Current seed data:

```text
api/seed_chunks.json
```

Count:

```text
73 legal chunks
```

### Weaviate Class

Class name:

```text
LegalChunk
```

Schema fields:

- `chunk_id`
- `source_name`
- `reference`
- `topic`
- `text`
- `source_page`
- `source_type`
- `jurisdiction`

Vectors are provided externally by the API seeding script. Weaviate does not vectorize text by itself.

### Citation Fields

Each citation returned by the API includes:

- `chunk_id`
- `source_name`
- `reference`
- `topic`
- `source_page`

## 10. How To Run On Windows

Recommended path for teammates: Windows PowerShell + Docker Desktop + Ollama Windows app.

Do not run this from WSL unless you know your Docker/Ollama networking.

Before running commands, make sure Docker Desktop is installed and running, Ollama for Windows is installed, and `qwen3:4b` is pulled locally. `jq` is optional on Windows; the documented commands do not require it.

```powershell
git clone <repo-url>
cd <repo-folder>
Copy-Item .env.example .env

ollama pull qwen3:4b
ollama list
curl.exe http://localhost:11434/api/tags

docker compose -p lawz-ai-jo up -d --build
docker compose -p lawz-ai-jo ps

curl.exe http://localhost:8001/healthz
curl.exe http://localhost:8001/readyz

docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate

curl.exe -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d "{\"question\":\"هل يجوز إنهاء عقد العمل بدون إشعار؟\",\"k\":5}"
```

Open:

```text
http://localhost:3001
```

## 11. How To Run On Linux

Ollama still runs on the host. Start Ollama and pull the model:

```bash
ollama pull qwen3:4b
curl http://localhost:11434/api/tags
```

Create `.env`:

```bash
cp .env.example .env
```

Start the stack:

```bash
docker compose -p lawz-ai-jo up -d --build
docker compose -p lawz-ai-jo ps
```

Check readiness:

```bash
curl http://localhost:8001/healthz
curl http://localhost:8001/readyz
```

Seed:

```bash
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

Ask:

```bash
curl -X POST http://localhost:8001/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"هل يجوز إنهاء عقد العمل بدون إشعار؟","k":5}'
```

## 12. Troubleshooting History

### Docker Ports Already Taken

Issue: Docker ports `8001`, `8081`, and `3001` were already taken by old `docker-proxy` processes from another Docker context.

Fix: Checked Docker contexts and stopped old main-repo containers that were still holding the ports.

Useful commands:

```bash
docker context ls
docker ps
docker compose -p <old-project-name> down
```

### Compose File Had `api` At Root Level

Issue: `docker-compose.yml` once had `api` at the root level and failed with:

```text
additional properties 'api' not allowed
```

Fix: Ensured `api` is nested under the top-level `services:` key.

### `/metrics` Redirects

Issue: `GET /metrics` returned a `307` redirect to `/metrics/`.

Fix: Use:

```bash
curl -L http://localhost:8001/metrics
```

or:

```bash
curl http://localhost:8001/metrics/
```

On Windows PowerShell, use `curl.exe`.

### Local Eval Missing `httpx`

Issue: The local evaluation script failed in `.venv` because `httpx` was missing.

Fix:

```bash
python -m pip install httpx
```

### Slow Generation

Issue: `qwen3:4b` generation was slow, taking around 2-4 minutes per answer.

Fix: Use a longer timeout for evaluation:

```bash
python eval_rag_smoke.py --api-url http://localhost:8001 --timeout 300 --output outputs/rag_smoke_results.json
```

## 13. Known Limitations

- Not legal advice.
- Small legal corpus.
- Small smoke evaluation.
- Slow local generation.
- Confidence score is approximate.
- LLM wording may need legal review.

## 14. Future Work

- Add 50+ hand-labeled evaluation questions.
- Improve confidence scoring.
- Explore faster generation options.
- Add a smaller model option.
- Improve frontend loading and progress feedback.
- Add a dataset card.
- Add optional contract upload later.
- Add optional report export later.
- Explore possible hosted deployment.

## 15. Appendix: Key Commands

### Start

```powershell
docker compose -p lawz-ai-jo up -d --build
```

### Stop

```powershell
docker compose -p lawz-ai-jo down
```

### Stop And Delete Weaviate Volume

```powershell
docker compose -p lawz-ai-jo down -v
```

### Check Services

```powershell
docker compose -p lawz-ai-jo ps
```

### API Health

```powershell
curl.exe http://localhost:8001/healthz
curl.exe http://localhost:8001/readyz
```

### Ollama Health

```powershell
curl.exe http://localhost:11434/api/tags
```

### Seed Weaviate

```powershell
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

### Ask A Question

```powershell
curl.exe -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d "{\"question\":\"هل يجوز إنهاء عقد العمل بدون إشعار؟\",\"k\":5}"
```

### Metrics

```powershell
curl.exe -L http://localhost:8001/metrics
```

### API Logs

```powershell
docker compose -p lawz-ai-jo logs api --tail=120
```

### Smoke Evaluation

```powershell
python eval_rag_smoke.py --api-url http://localhost:8001 --timeout 300 --output outputs/rag_smoke_results.json
```
