import os

os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")

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


def test_diagnostics_state():
    resp = client.get('/diagnostics/state')
    assert resp.status_code == 200
    assert 'active_tasks' in resp.json()
