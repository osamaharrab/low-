import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("pydantic")
    pytest.importorskip("pydantic_settings")
    pytest.importorskip("prometheus_client")

    from fastapi.testclient import TestClient

    from api.main import app

    def ok_weaviate(settings):
        return {"ok": True, "status_code": 200, "url": settings.weaviate_url}

    def ok_ollama(settings):
        return {"ok": True, "status_code": 200, "url": settings.ollama_base_url}

    def ok_llm(settings):
        return {"ok": True, "provider": settings.llm_provider}

    def ok_neo4j(settings):
        return {"ok": True, "uri": settings.neo4j_uri, "database": settings.neo4j_database}

    monkeypatch.setattr("api.main.check_weaviate_ready", ok_weaviate)
    monkeypatch.setattr("api.main.check_ollama_ready", ok_ollama)
    monkeypatch.setattr("api.main.check_llm_ready", ok_llm)
    monkeypatch.setattr("api.main.check_neo4j_ready", ok_neo4j)
    with TestClient(app) as test_client:
        yield test_client
