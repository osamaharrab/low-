# Windows Quickstart

Recommended path for teammates: Windows PowerShell + Docker Desktop + Ollama Windows app.

Do not run this from WSL unless you know your Docker/Ollama networking.

## 1. Install Docker Desktop

Install Docker Desktop for Windows and make sure it is running with Linux containers / WSL2 backend.

## 2. Install Ollama For Windows

Install Ollama for Windows and open it from the Start Menu.

## 3. Pull The Model

```powershell
ollama pull qwen3:4b
ollama list
```

`jq` is optional on Windows and is not required for these commands.

## 4. Clone The Repo

```powershell
git clone <repo-url>
cd <repo-folder>
```

## 5. Copy The Env File

```powershell
Copy-Item .env.example .env
```

## 6. Run The Stack

```powershell
docker compose -p lawz-ai-jo up -d --build
```

## 7. Seed Weaviate

```powershell
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

## 8. Open The App

```text
http://localhost:3001
```

The first answer may be slow. `qwen3:4b` can take 2-4 minutes per question on local machines.

## If It Fails

Check Ollama:

```powershell
curl.exe http://localhost:11434/api/tags
```

Check API readiness:

```powershell
curl.exe http://localhost:8001/readyz
```

Check API logs:

```powershell
docker compose -p lawz-ai-jo logs api --tail=120
```

Stop the stack:

```powershell
docker compose -p lawz-ai-jo down
```
