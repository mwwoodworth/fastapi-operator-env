from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    resp = client.get('/health')
    assert resp.status_code == 200


def test_registry():
    resp = client.get('/docs/registry')
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
