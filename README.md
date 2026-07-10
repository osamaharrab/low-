# Lawz AI JO

Lawz AI JO is an Arabic Retrieval-Augmented Generation (RAG) assistant for Jordanian labor-law information. It is an informational legal explainer, not a lawyer and not legal advice.

The project is intentionally focused. It answers questions about Jordanian labor/employment law using retrieved local legal chunks, then generates a grounded Arabic answer with backend-generated citations.

## What It Does

- Takes Arabic labor-law questions from the web UI or API.
- Embeds the question with `intfloat/multilingual-e5-small`.
- Retrieves relevant Jordanian labor-law chunks from Weaviate.
- Reranks retrieved chunks with a small lexical-overlap boost.
- Calls the configured LLM provider.
- Returns a clean Arabic answer, backend-generated citations, retrieved chunk previews, confidence, and a legal disclaimer.
- Returns an insufficient-evidence answer when the retrieved context is not enough.
- Clears citations for insufficient or weak-evidence answers so unrelated references are not shown.
- Provides a separate Neo4j Text2Cypher Knowledge Graph proof of concept at `POST /kg/query`.

## What It Does Not Do

- No PDF upload.
- No DOCX parsing.
- No contract review.
- No risk scoring.
- No broad GraphRAG rebuild.
- No LangChain.
- No broad legal-chatbot behavior.
- No production legal-advice workflow.

## Current LLM Provider

The primary fast generation path is xAI / Grok:

```env
LLM_PROVIDER=xai
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-4.3
```

Ollama is still available as a local option:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b
```

Do not use a Groq key here. xAI keys usually start with `xai-` and must be sent to `https://api.x.ai/v1`.

## Architecture

```text
User
  -> Web UI
  -> FastAPI /rag/answer
  -> question embedding
  -> Weaviate LegalChunk retrieval
  -> reranked legal chunks
  -> grounded Arabic prompt
  -> xAI/Grok or Ollama
  -> answer + backend citations + disclaimer
```

Citations are created by the backend from retrieved chunks. The LLM is not trusted to invent or format citations.

## Knowledge Graph Proof Of Concept

The KG feature is separate from the stable RAG pipeline. It does not modify retrieval, embeddings, Weaviate, RAG prompts, RAG responses, or RAG evaluation.

Architecture:

```text
Natural-language question
  -> FastAPI POST /kg/query
  -> schema-bounded LLM Cypher generation
  -> Cypher extraction
  -> read-only Cypher validation
  -> Neo4j execution
  -> records + nodes + relationships + generated Cypher + Arabic summary
```

Important files:

- `api/kg.py`
- `api/seed_neo4j.py`
- `api/seed_graph.json`
- `data/kg_questions.json`
- `eval_kg.py`
- `web/pages/kg.js`

Environment variables:

```env
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change_me_neo4j_password
NEO4J_DATABASE=neo4j
KG_QUERY_LIMIT=25
KG_TIMEOUT_SECONDS=15
KG_MAX_CYPHER_CHARS=4000
```

Start the stack:

```powershell
docker compose -p lawz-ai-jo up -d --build
```

Open Neo4j Browser:

```text
http://localhost:7474
```

Seed the graph scaffold:

```powershell
docker compose -p lawz-ai-jo exec -T api python -m api.seed_neo4j
```

Ask the KG endpoint:

```powershell
curl.exe -X POST http://localhost:8001/kg/query -H "Content-Type: application/json" -d "{\"question\":\"ما المواد المرتبطة بإنهاء عقد العمل؟\"}"
```

Run KG evaluation:

```powershell
python eval_kg.py --api-url http://localhost:8001 --fixture data/kg_questions.json --output outputs/kg_eval_results.json
```

`data/kg_questions.json` is intentionally an empty JSON array until the KG owner adds reviewed fixtures. Example shape:

```json
[
  {
    "question": "ما المواد المرتبطة بإنهاء عقد العمل؟",
    "gold_cypher": "MATCH (law:Law)-[:HAS_ARTICLE]->(article:Article) WHERE article.title CONTAINS 'إنهاء' RETURN law, article LIMIT $limit"
  }
]
```

Teammate ownership boundary: `api/kg.py` contains `TODO(KG teammate):` sections for final schema, prompt, extraction, validation, execution, serialization, and orchestration logic. `api/seed_neo4j.py` contains `TODO(KG data owner):` sections for reviewed legal graph data. Do not claim this KG proof of concept is complete while those TODOs remain.

Never commit the real `.env` file or a real `XAI_API_KEY`.

## Services And Ports

| Service | URL | Notes |
| --- | --- | --- |
| Web UI | http://localhost:3001 | Next.js UI |
| API | http://localhost:8001 | FastAPI |
| Weaviate | http://localhost:8081 | Vector database |
| Neo4j Browser | http://localhost:7474 | Knowledge graph database |
| Neo4j Bolt | bolt://localhost:7687 | Driver connection |
| Metrics | http://localhost:8001/metrics/ | Prometheus text |
| Ollama | http://localhost:11434 | Only needed when `LLM_PROVIDER=ollama` |

## Answer Format

For in-scope legal questions, the answer is prompted to use this structure:

```text
الإجابة المختصرة:
...

التفسير:
...

المراجع:
- ...
- ...

تنبيه:
هذا شرح أولي وليس استشارة قانونية.
```

For out-of-scope questions or weak evidence, the API should return an insufficient-evidence answer and empty citations:

```json
{
  "answer": "لا تكفي قاعدة المعرفة الحالية للإجابة بثقة.",
  "citations": [],
  "confidence": 0.0,
  "retrieved_chunks": [],
  "disclaimer": "..."
}
```

`retrieved_chunks` may still be present for debugging/evaluation if Weaviate returned chunks, but unrelated citations are not shown.

## Windows Prerequisites

- Windows 10 or Windows 11.
- Docker Desktop installed and running.
- Docker Desktop using Linux containers / WSL2 backend.
- Git installed.
- xAI API key for the recommended fast path.
- Optional: Ollama for Windows and `qwen3:4b` if using local generation.

## Windows Setup With PowerShell

Clone the repo:

```powershell
git clone <repo-url>
cd <repo-folder>
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set your xAI key:

```env
LLM_PROVIDER=xai
XAI_API_KEY=your_xai_api_key_here
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-4.3
```

Start the Docker stack:

```powershell
docker compose -p lawz-ai-jo up -d --build
docker compose -p lawz-ai-jo ps
```

Check the API:

```powershell
curl.exe http://localhost:8001/healthz
curl.exe http://localhost:8001/readyz
```

Seed Weaviate:

```powershell
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

Ask a legal test question:

```powershell
curl.exe -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d "{\"question\":\"هل يجوز إنهاء عقد العمل بدون إشعار؟\",\"k\":5}"
```

Ask an out-of-scope test question:

```powershell
curl.exe -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d "{\"question\":\"ما هي أفضل طريقة لتعلم بايثون؟\",\"k\":5}"
```

Open the app:

```text
http://localhost:3001
```

## Environment File

Start from:

```powershell
Copy-Item .env.example .env
```

Recommended values:

```env
WEAVIATE_URL=http://weaviate:8080
WEAVIATE_CLASS=LegalChunk
EMBEDDING_MODEL=intfloat/multilingual-e5-small
TOP_K=5
RAG_PROMPT_TOP_N=3
CHUNK_TEXT_LIMIT=900

# LLM provider: "xai" for Grok API, "ollama" for local generation.
LLM_PROVIDER=xai
LLM_TIMEOUT_SECONDS=30
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=650

# xAI / Grok API
XAI_API_KEY=your_xai_api_key_here
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-4.3

# Ollama local option
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=120

NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change_me_neo4j_password
NEO4J_DATABASE=neo4j
KG_QUERY_LIMIT=25
KG_TIMEOUT_SECONDS=15
KG_MAX_CYPHER_CHARS=4000

API_URL=http://api:8000
NEXT_PUBLIC_API_URL=http://localhost:8001

WEB_ORIGIN=http://localhost:3001
```

Do not commit `.env`.

## Switching To Ollama

Use this only if you want local generation instead of xAI:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=120
```

Then make sure Ollama is running on the host:

```powershell
ollama pull qwen3:4b
ollama list
curl.exe http://localhost:11434/api/tags
```

Local `qwen3:4b` can be slow. Some answers may take 2-4 minutes depending on the machine.

## Readiness

`/readyz` checks:

- Weaviate readiness.
- Neo4j readiness with `RETURN 1 AS ok`.
- The selected LLM provider configuration.

For xAI, readiness does not call the generation API and does not spend tokens. It only checks that:

- `XAI_API_KEY` is configured.
- `XAI_BASE_URL` is configured.
- `XAI_MODEL` is configured.

Check readiness:

```powershell
curl.exe http://localhost:8001/readyz
```

## API

Main endpoint:

```text
POST /rag/answer
```

Request:

```json
{
  "question": "هل يجوز إنهاء عقد العمل بدون إشعار؟",
  "k": 5
}
```

Response:

```json
{
  "answer": "...",
  "citations": [],
  "confidence": 0.0,
  "retrieved_chunks": [],
  "disclaimer": "..."
}
```

The response shape is stable for the web UI and evaluation script.

KG endpoint:

```text
POST /kg/query
```

Request:

```json
{
  "question": "ما المواد المرتبطة بإنهاء عقد العمل؟"
}
```

Response includes:

- `answer`
- `generated_cypher`
- `parameters`
- `records`
- `nodes`
- `relationships`
- `row_count`
- `disclaimer`

## Web UI

The web UI:

- Uses RTL Arabic layout.
- Preserves line breaks in generated answers.
- Shows citations only when the backend returns them.
- Shows a subtle no-citations message for insufficient evidence.
- Keeps retrieved chunks available in a collapsed section.
- Shows loading and error states.

Open:

```text
http://localhost:3001
```

## Metrics

Prometheus-style metrics are exposed at:

```text
http://localhost:8001/metrics/
```

Test from PowerShell:

```powershell
curl.exe -L http://localhost:8001/metrics
```

Useful metric names include:

- `requests_total`
- `request_latency_seconds`
- `inflight_requests`
- `rag_answers_total`
- `rag_retrieved_chunks`
- `rag_generation_errors_total`
- `kg_queries_total`
- `kg_rows_returned`
- `kg_generation_errors_total`
- `kg_validation_errors_total`
- `kg_execution_errors_total`

To see the counters move, call `/rag/answer` once, then check `/metrics` again.

## Evaluation

Run the smoke evaluation after the stack is running and Weaviate is seeded:

```powershell
python eval_rag_smoke.py --api-url http://localhost:8001 --timeout 300 --output outputs/rag_smoke_results.json
```

If Python cannot import `httpx` locally:

```powershell
python -m pip install httpx
```

The evaluation fixture is `data/rag_smoke.json`. The generated report is written under `outputs/`, which should not be committed.

Run the KG Text2Cypher evaluation after the stack is running and Neo4j is reachable:

```powershell
python eval_kg.py --api-url http://localhost:8001 --fixture data/kg_questions.json --output outputs/kg_eval_results.json
```

The KG fixture starts empty on purpose. Add reviewed question/gold Cypher pairs before using the results as a meaningful quality signal.

## Validation Commands

Safe local validation commands:

```bash
python -m compileall -q api tests eval_kg.py eval_rag_smoke.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
docker compose config --services
```

These commands do not run live xAI calls, do not start Docker containers, and do not seed Weaviate.

## Common Issues

- xAI returns `401`: confirm `LLM_PROVIDER=xai`, `XAI_API_KEY` starts with `xai-`, and `XAI_BASE_URL=https://api.x.ai/v1`.
- `/readyz` says LLM is not ready: check that `.env` has `XAI_API_KEY`, `XAI_BASE_URL`, and `XAI_MODEL`.
- Port already in use: stop the other service using ports `3001`, `8001`, `8081`, or `11434`.
- Docker Desktop not running: start Docker Desktop and wait until it is ready.
- Neo4j is not ready: set `NEO4J_PASSWORD` in `.env`, rebuild/start the stack, and check `http://localhost:7474`.
- Weaviate returns no useful answers: make sure seeding was run with `python -m api.seed_weaviate` inside the API container.
- `/metrics` redirects to `/metrics/`: use `curl.exe -L http://localhost:8001/metrics` or open `http://localhost:8001/metrics/`.
- `jq` may not be installed on Windows. It is optional.

## Stop Or Reset

Stop containers:

```powershell
docker compose -p lawz-ai-jo down
```

Delete containers and the Weaviate/Neo4j volumes:

```powershell
docker compose -p lawz-ai-jo down -v
```

## GitHub Safety

Do not commit local or generated files such as:

- `.env`
- `.venv/`
- `node_modules/`
- `.next/`
- `outputs/`
- `__pycache__/`
- `.pytest_cache/`

Never commit real API keys.

## More Documentation

- [Windows Quickstart](docs/WINDOWS_QUICKSTART.md)
- [Project Guide](docs/PROJECT_GUIDE.md)

## License

MIT
