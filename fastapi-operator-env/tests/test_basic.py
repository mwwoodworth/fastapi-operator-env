import os

os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("TANA_API_KEY", "test")
os.environ.setdefault("VERCEL_TOKEN", "test")
os.environ.setdefault("INBOX_SUMMARIZER_MODEL", "none")
os.environ.setdefault("PUSH_WEBHOOK_URL", "")
os.environ.setdefault("MEMORY_SYNC_AGENT", "true")
os.environ.setdefault("AI_COAUTHOR_MODE", "enabled")
os.environ.setdefault("AI_FEEDBACK_CHAIN", "true")
os.environ.setdefault("FORECAST_PLANNER_ENABLED", "true")
os.environ.setdefault("WEEKLY_STRATEGY_DAY", "Sunday")
os.environ.setdefault("DAILY_PLANNER_MODEL", "claude")
os.environ.setdefault("ESCALATION_CHECK_INTERVAL", "1800")
os.environ.setdefault("SLACK_WEBHOOK_URL", "http://example.com/webhook")

from passlib.hash import pbkdf2_sha256
os.environ["AUTH_USERS"] = '{"user":"' + pbkdf2_sha256.hash("pass") + '","agent":"' + pbkdf2_sha256.hash("secret") + '"}'
import importlib
from fastapi.testclient import TestClient
import main as main_module


def auth_client():
    os.environ["AUTH_USERS"] = '{"user":"' + pbkdf2_sha256.hash("pass") + '","agent":"' + pbkdf2_sha256.hash("secret") + '"}'
    importlib.reload(main_module)
    c = TestClient(main_module.app)
    resp = c.post(
        "/auth/token",
        data={"username": "user", "password": "pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return TestClient(main_module.app), {"Authorization": f"Bearer {token}"}


def test_health():
    client, headers = auth_client()
    resp = client.get("/health", headers=headers)
    assert resp.status_code == 200


def test_registry():
    client, headers = auth_client()
    resp = client.get("/docs/registry", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_diagnostics_state():
    client, headers = auth_client()
    resp = client.get("/diagnostics/state", headers=headers)
    assert resp.status_code == 200
    assert "active_tasks" in resp.json()


def test_voice_endpoints():
    client, headers = auth_client()
    resp = client.get("/voice/history", headers=headers)
    assert resp.status_code == 200
    resp = client.get("/voice/status", headers=headers)
    assert resp.status_code == 200


def test_inbox_routes():
    client, headers = auth_client()
    from codex.memory import agent_inbox

    item = agent_inbox.add_to_inbox("sample_task", {"foo": "bar"}, "test")
    resp = client.get("/agent/inbox", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    tasks = data.get("tasks", [])
    assert isinstance(tasks, list)
    assert any(t["task_id"] == item["task_id"] for t in tasks)
    resp = client.post(
        "/agent/inbox/approve",
        json={"task_id": item["task_id"], "decision": "reject"},
        headers=headers,
    )
    assert resp.status_code == 200
    resp = client.get("/agent/inbox/summary", headers=headers)
    assert resp.status_code == 200


def test_new_agent_routes():
    client, headers = auth_client()
    resp = client.post("/agent/plan/daily", headers=headers)
    assert resp.status_code == 200
    resp = client.post("/agent/inbox/prioritize", headers=headers)
    assert resp.status_code == 200
    resp = client.get("/agent/inbox/mobile", headers=headers)
    assert resp.status_code == 200


def test_recurring_and_delay_routes():
    client, headers = auth_client()
    # add recurring task
    payload = {
        "task": "claude_prompt",
        "context": {"prompt": "test"},
        "frequency": "weekly",
        "day": "Monday",
        "time": "08:00",
    }
    resp = client.post("/agent/recurring/add", json=payload, headers=headers)
    assert resp.status_code == 200
    resp = client.get("/agent/recurring", headers=headers)
    assert resp.status_code == 200
    # delay inbox task
    from codex.memory import agent_inbox

    item = agent_inbox.add_to_inbox("sample_task", {"foo": "bar"}, "test")
    resp = client.post(
        "/agent/inbox/delay",
        json={"task_id": item["task_id"], "delay_until": "2100-01-01T00:00"},
        headers=headers,
    )
    assert resp.status_code == 200
    resp = client.get("/dashboard/tasks", headers=headers)
    assert resp.status_code == 200


def test_new_phase16_routes():
    client, headers = auth_client()
    resp = client.post("/memory/sync/agents", headers=headers)
    assert resp.status_code == 200

    resp = client.post("/task/ai-coauthor", json={"intent": "test"}, headers=headers)
    assert resp.status_code == 200

    resp = client.post("/agent/workflows/audit", headers=headers)
    assert resp.status_code == 200

    resp = client.post(
        "/memory/audit/diff", json={"task_id": "claude_prompt"}, headers=headers
    )
    assert resp.status_code == 200

    resp = client.get("/dashboard/sync", headers=headers)
    assert resp.status_code == 200


def test_new_phase17_routes():
    client, headers = auth_client()
    resp = client.post("/agent/forecast/weekly", headers=headers)
    assert resp.status_code == 200

    resp = client.get("/dashboard/forecast", headers=headers)
    assert resp.status_code == 200

    resp = client.post("/agent/strategy/weekly", headers=headers)
    assert resp.status_code == 200

    resp = client.post(
        "/task/dependency-map",
        json={"tasks": [{"task": "A"}, {"task": "B", "depends_on": "A"}]},
        headers=headers,
    )
    assert resp.status_code == 200


def test_phase18_knowledge_routes():
    client, headers = auth_client()
    resp = client.post("/knowledge/index", headers=headers)
    assert resp.status_code == 200

    resp = client.post(
        "/knowledge/query",
        json={"query": "Claude recommended", "sources": ["local_docs"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "summary" in resp.json()

    resp = client.get("/knowledge/sources", headers=headers)
    assert resp.status_code == 200

    resp = client.get("/logs/rag", headers=headers)
    assert resp.status_code == 200


def test_knowledge_vector_routes():
    client, headers = auth_client()
    resp = client.post(
        "/knowledge/doc/upload", json={"content": "hello world"}, headers=headers
    )
    assert resp.status_code == 200

    resp = client.get("/knowledge/search?q=hello", headers=headers)
    assert resp.status_code == 200
    assert "results" in resp.json()


def test_dashboard_metrics():
    client, headers = auth_client()
    resp = client.get("/dashboard/metrics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks_logged" in data


def test_dashboard_ops():
    client, headers = auth_client()
    resp = client.get("/dashboard/ops", headers=headers)
    assert resp.status_code == 200
    assert "sales" in resp.json()


def test_search_and_error_logs():
    client, headers = auth_client()
    resp = client.get("/memory/search?q=test", headers=headers)
    assert resp.status_code == 200
    assert "entries" in resp.json()

    resp = client.get("/logs/errors", headers=headers)
    assert resp.status_code == 200
    assert "entries" in resp.json()


def test_jwt_auth_enforced():
    os.environ["AUTH_USERS"] = '{"user":"' + pbkdf2_sha256.hash("pass") + '"}'
    os.environ["ADMIN_USERS"] = "user"
    import importlib
    import main as main_module

    importlib.reload(main_module)
    c = TestClient(main_module.app)
    resp = c.get("/health")
    assert resp.status_code == 401
    token_resp = c.post(
        "/auth/token",
        data={"username": "user", "password": "pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]
    resp = c.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
