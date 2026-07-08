# Lawz AI JO

Lawz AI JO is an Arabic Retrieval-Augmented Generation (RAG) assistant for Jordanian labor-law information. It is an informational legal explainer, not a lawyer and not legal advice.

## What It Does

- Takes Arabic legal-information questions from the web UI or API.
- Retrieves relevant Jordanian labor-law chunks from Weaviate.
- Calls local Ollama with `qwen3:4b`.
- Returns an Arabic answer, backend-generated citations, retrieved chunk previews, confidence, and a legal disclaimer.

## What It Does Not Do

- No PDF upload.
- No DOCX parsing.
- No contract review.
- No risk scoring.
- No Neo4j.
- No knowledge graph.
- No paid APIs.
- Not a broad legal chatbot.

## Architecture

```text
User -> Web UI -> FastAPI -> Weaviate -> retrieved chunks -> Ollama qwen3:4b -> answer/citations
```

Ollama does not run inside Docker. It must run on your host machine. The API container reaches it with:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

## Services And Ports

| Service | URL |
| --- | --- |
| Web UI | http://localhost:3001 |
| API | http://localhost:8001 |
| Weaviate | http://localhost:8081 |
| Ollama | http://localhost:11434 |

## Windows Prerequisites

- Windows 10 or Windows 11.
- Docker Desktop installed and running.
- Docker Desktop using Linux containers / WSL2 backend.
- Ollama for Windows installed.
- Git installed.
- `qwen3:4b` pulled in Ollama.

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

Install the local Ollama model:

```powershell
ollama pull qwen3:4b
ollama list
curl.exe http://localhost:11434/api/tags
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

Ask a test question:

```powershell
curl.exe -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d "{\"question\":\"هل يجوز إنهاء عقد العمل بدون إشعار؟\",\"k\":5}"
```

Open the app:

```text
http://localhost:3001
```

`qwen3:4b` can be slow on local machines. Some answers may take 2-4 minutes.

## Environment File

Start from:

```powershell
Copy-Item .env.example .env
```

Default values:

```env
WEAVIATE_URL=http://weaviate:8080
WEAVIATE_CLASS=LegalChunk
EMBEDDING_MODEL=intfloat/multilingual-e5-small
TOP_K=5
RAG_PROMPT_TOP_N=3
CHUNK_TEXT_LIMIT=900

OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=120

API_URL=http://api:8000
NEXT_PUBLIC_API_URL=http://localhost:8001

WEB_ORIGIN=http://localhost:3001
```

Do not commit `.env`.

## If `/readyz` Says Ollama Is Not Ready

1. Check Ollama is reachable from Windows:

   ```powershell
   curl.exe http://localhost:11434/api/tags
   ```

2. Open the Ollama app from the Start Menu.

3. Check and pull the model:

   ```powershell
   ollama list
   ollama pull qwen3:4b
   ```

4. Restart Docker Desktop.

5. Restart the stack:

   ```powershell
   docker compose -p lawz-ai-jo down
   docker compose -p lawz-ai-jo up -d --build
   ```

6. Optional advanced local-development step: if the API container still cannot reach Ollama on Windows, create a user environment variable:

   ```text
   OLLAMA_HOST=0.0.0.0:11434
   ```

   Then quit Ollama from the taskbar and start it again from the Start Menu. Use this only for trusted local development.

## Common Issues

- Port already in use: stop the other service using ports `3001`, `8001`, `8081`, or `11434`.
- Docker Desktop not running: start Docker Desktop and wait until it is ready.
- Ollama model missing: run `ollama pull qwen3:4b`.
- First API call is slow: the embedding model and generator may warm up.
- Smoke evaluation takes time: `qwen3:4b` may take 2-4 minutes per question.
- `/metrics` redirects to `/metrics/`: use `curl.exe -L http://localhost:8001/metrics` or open `http://localhost:8001/metrics/`.
- `jq` may not be installed on Windows. It is optional.

## Stop Or Reset

Stop containers:

```powershell
docker compose -p lawz-ai-jo down
```

Delete containers and the Weaviate volume:

```powershell
docker compose -p lawz-ai-jo down -v
```

## Evaluation

Run the smoke evaluation after the stack is running and Weaviate is seeded:

```powershell
python eval_rag_smoke.py --api-url http://localhost:8001 --timeout 300 --output outputs/rag_smoke_results.json
```

If Python cannot import `httpx` on Windows, install it locally:

```powershell
python -m pip install httpx
```

The evaluation fixture is `data/rag_smoke.json`. The generated report is written under `outputs/`, which should not be committed.

## GitHub Safety

Do not commit local or generated files such as:

- `.env`
- `.venv/`
- `node_modules/`
- `.next/`
- `outputs/`
- `__pycache__/`
- `.pytest_cache/`

## More Documentation

- [Windows Quickstart](docs/WINDOWS_QUICKSTART.md)
- [Project Guide](docs/PROJECT_GUIDE.md)

## License

MIT
