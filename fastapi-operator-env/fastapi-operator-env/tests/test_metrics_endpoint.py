from tests.test_basic import auth_client


def test_metrics_endpoint():
    client, _ = auth_client()
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
