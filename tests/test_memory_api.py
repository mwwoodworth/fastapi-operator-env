import os
import importlib
from fastapi.testclient import TestClient

os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("TANA_API_KEY", "test")
os.environ.setdefault("VERCEL_TOKEN", "test")
os.environ["AUTH_USERS"] = '{"user":"pass"}'
os.environ.pop("ADMIN_USERS", None)
import main as main_module

importlib.reload(main_module)
client = TestClient(main_module.app)


def _auth_client():
    importlib.reload(main_module)
    c = TestClient(main_module.app)
    token_resp = c.post(
        "/auth/token",
        data={"username": "user", "password": "pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]
    return TestClient(main_module.app), {"Authorization": f"Bearer {token}"}


def test_memory_write_and_query():
    client, headers = _auth_client()
    payload = {
        "project_id": "test_proj",
        "title": "Test Doc",
        "content": "hello world",
        "author_id": "tester",
    }
    resp = client.post("/memory/write", json=payload, headers=headers)
    assert resp.status_code == 200
    doc_id = resp.json()["document_id"]

    q = client.post("/memory/query", json={"query": "hello"}, headers=headers)
    assert q.status_code == 200
    assert q.json()["results"]


def test_gemini_sync_route():
    client, headers = _auth_client()
    resp = client.post(
        "/memory/gemini-sync", json={"values": ["a", "b"]}, headers=headers
    )
    assert resp.status_code == 200
