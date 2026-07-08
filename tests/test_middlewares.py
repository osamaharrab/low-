def test_request_id_header_is_returned(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_readyz_can_be_monkeypatched(client):
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
