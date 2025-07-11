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
os.environ.pop("BASIC_AUTH_USERS", None)
os.environ.pop("ADMIN_USERS", None)
import main as main_module

importlib.reload(main_module)
client = TestClient(main_module.app)


def test_memory_write_and_query():
    os.environ.pop("BASIC_AUTH_USERS", None)
    os.environ.pop("ADMIN_USERS", None)
    importlib.reload(main_module)
    c = TestClient(main_module.app)
    payload = {
        "project_id": "test_proj",
        "title": "Test Doc",
        "content": "hello world",
        "author_id": "tester",
    }
    resp = c.post("/memory/write", json=payload)
    assert resp.status_code == 200
    doc_id = resp.json()["document_id"]

    q = c.post("/memory/query", json={"query": "hello"})
    assert q.status_code == 200
    assert q.json()["results"]


def test_gemini_sync_route():
    os.environ.pop("BASIC_AUTH_USERS", None)
    os.environ.pop("ADMIN_USERS", None)
    importlib.reload(main_module)
    c = TestClient(main_module.app)
    resp = c.post("/memory/gemini-sync", json={"values": ["a", "b"]})
    assert resp.status_code == 200
