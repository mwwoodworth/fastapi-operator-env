import os

os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
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


def test_recurring_and_delay_routes():
    # add recurring task
    payload = {
        "task": "claude_prompt",
        "context": {"prompt": "test"},
        "frequency": "weekly",
        "day": "Monday",
        "time": "08:00"
    }
    resp = client.post('/agent/recurring/add', json=payload)
    assert resp.status_code == 200
    resp = client.get('/agent/recurring')
    assert resp.status_code == 200
    # delay inbox task
    from codex.memory import agent_inbox
    item = agent_inbox.add_to_inbox("sample_task", {"foo": "bar"}, "test")
    resp = client.post('/agent/inbox/delay', json={"task_id": item["task_id"], "delay_until": "2100-01-01T00:00"})
    assert resp.status_code == 200
    resp = client.get('/dashboard/tasks')
    assert resp.status_code == 200


def test_new_phase16_routes():
    resp = client.post('/memory/sync/agents')
    assert resp.status_code == 200

    resp = client.post('/task/ai-coauthor', json={"intent": "test"})
    assert resp.status_code == 200

    resp = client.post('/agent/workflows/audit')
    assert resp.status_code == 200

    resp = client.post('/memory/audit/diff', json={"task_id": "claude_prompt"})
    assert resp.status_code == 200

    resp = client.get('/dashboard/sync')
    assert resp.status_code == 200


def test_new_phase17_routes():
    resp = client.post('/agent/forecast/weekly')
    assert resp.status_code == 200

    resp = client.get('/dashboard/forecast')
    assert resp.status_code == 200

    resp = client.post('/agent/strategy/weekly')
    assert resp.status_code == 200

    resp = client.post(
        '/task/dependency-map',
        json={"tasks": [{"task": "A"}, {"task": "B", "depends_on": "A"}]},
    )
    assert resp.status_code == 200


def test_phase18_knowledge_routes():
    resp = client.post('/knowledge/index')
    assert resp.status_code == 200

    resp = client.post(
        '/knowledge/query',
        json={"query": "Claude recommended", "sources": ["local_docs"]},
    )
    assert resp.status_code == 200
    assert 'summary' in resp.json()

    resp = client.get('/knowledge/sources')
    assert resp.status_code == 200

    resp = client.get('/logs/rag')
    assert resp.status_code == 200


def test_dashboard_metrics():
    resp = client.get('/dashboard/metrics')
    assert resp.status_code == 200
    data = resp.json()
    assert 'tasks_logged' in data


def test_search_and_error_logs():
    resp = client.get('/memory/search?q=test')
    assert resp.status_code == 200
    assert 'entries' in resp.json()

    resp = client.get('/logs/errors')
    assert resp.status_code == 200
    assert 'entries' in resp.json()


def test_basic_auth_enforced():
    os.environ['BASIC_AUTH_USERS'] = '{"user":"pass"}'
    os.environ['ADMIN_USERS'] = 'user'
    import importlib
    import main as main_module
    importlib.reload(main_module)
    auth_client = TestClient(main_module.app)
    resp = auth_client.get('/health')
    assert resp.status_code == 401
    resp = auth_client.get('/health', auth=("user", "pass"))
    assert resp.status_code == 200
