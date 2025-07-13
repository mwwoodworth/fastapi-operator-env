import importlib
from fastapi.testclient import TestClient

import os

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("TANA_API_KEY", "test")
os.environ.setdefault("VERCEL_TOKEN", "test")

import celery_app

celery_app.celery_app.conf.broker_url = "memory://"
celery_app.celery_app.conf.result_backend = "cache+memory://"
celery_app.celery_app.conf.task_store_eager_result = True

# Run tasks synchronously for tests
celery_app.celery_app.conf.task_always_eager = True

import main as main_module


def get_client():
    from passlib.hash import pbkdf2_sha256
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


def test_long_task_flow():
    client, headers = get_client()
    resp = client.post("/tasks/long", json={"duration": 1}, headers=headers)
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    status = client.get(f"/task/status/{task_id}", headers=headers)
    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "SUCCESS"
    assert data["result"]["duration"] == 1
