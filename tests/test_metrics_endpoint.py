def test_metrics_endpoint_exposes_prometheus_text(client):
    client.get("/healthz")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "requests_total" in response.text or "request_latency_seconds" in response.text


def test_healthz_returns_200(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "lawz-ai-jo-api"}
