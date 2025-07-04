import os

os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("INBOX_SUMMARIZER_MODEL", "none")
os.environ.setdefault("PUSH_WEBHOOK_URL", "")

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


def test_voice_endpoints():
    resp = client.get('/voice/history')
    assert resp.status_code == 200
    resp = client.get('/voice/status')
    assert resp.status_code == 200


def test_inbox_routes():
    from codex.memory import agent_inbox

    item = agent_inbox.add_to_inbox("sample_task", {"foo": "bar"}, "test")
    resp = client.get('/agent/inbox')
    assert resp.status_code == 200
    tasks = resp.json()
    assert isinstance(tasks, list)
    assert any(t["task_id"] == item["task_id"] for t in tasks)
    resp = client.post('/agent/inbox/approve', json={"task_id": item["task_id"], "decision": "reject"})
    assert resp.status_code == 200
    resp = client.get('/agent/inbox/summary')
    assert resp.status_code == 200

def test_new_agent_routes():
    resp = client.post('/agent/plan/daily')
    assert resp.status_code == 200
    resp = client.post('/agent/inbox/prioritize')
    assert resp.status_code == 200
    resp = client.get('/agent/inbox/mobile')
    assert resp.status_code == 200
