import os
import importlib
from io import BytesIO
from fastapi.testclient import TestClient

os.environ["AUTH_USERS"] = '{"agent":"secret"}'
os.environ.pop("ADMIN_USERS", None)
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("TANA_API_KEY", "test")
os.environ.setdefault("VERCEL_TOKEN", "test")

import chat_task_api

importlib.reload(chat_task_api)
import main as main_module

importlib.reload(main_module)


def get_client():
    os.environ["AUTH_USERS"] = '{"agent":"secret"}'
    importlib.reload(chat_task_api)
    importlib.reload(main_module)
    import db.session

    db.session.init_db()
    c = TestClient(main_module.app)
    resp = c.post(
        "/auth/token",
        data={"username": "agent", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return TestClient(main_module.app), {"Authorization": f"Bearer {token}"}


def test_thread_and_message_lifecycle():
    client, headers = get_client()
    t_resp = client.post("/threads", json={"title": "Test"}, headers=headers)
    assert t_resp.status_code == 200
    thread_id = t_resp.json()["id"]

    m_resp = client.post(
        "/messages",
        json={"thread_id": thread_id, "sender": "me", "content": "hi"},
        headers=headers,
    )
    assert m_resp.status_code == 200
    msg_id = m_resp.json()["id"]

    list_resp = client.get(f"/messages?thread={thread_id}", headers=headers)
    assert list_resp.status_code == 200
    assert any(m["id"] == msg_id for m in list_resp.json())

    patch = client.patch(
        f"/messages/{msg_id}", json={"content": "edited"}, headers=headers
    )
    assert patch.status_code == 200
    del_resp = client.delete(f"/messages/{msg_id}", headers=headers)
    assert del_resp.status_code == 200


def test_task_and_file_endpoints():
    client, headers = get_client()
    t_resp = client.post("/threads", json={"title": "TaskThread"}, headers=headers)
    thread_id = t_resp.json()["id"]
    task_resp = client.post(
        "/tasks",
        json={
            "title": "Do",
            "description": "d",
            "assigned_to": "a",
            "created_by": "a",
            "thread_id": thread_id,
        },
        headers=headers,
    )
    assert task_resp.status_code == 200
    task_id = task_resp.json()["id"]

    list_resp = client.get(f"/tasks?thread={thread_id}", headers=headers)
    assert any(t["id"] == task_id for t in list_resp.json())

    upd = client.patch(f"/tasks/{task_id}", json={"status": "done"}, headers=headers)
    assert upd.status_code == 200

    file_resp = client.post(
        "/files",
        headers=headers,
        data={"uploader": "me", "thread_id": str(thread_id)},
        files={"file": ("test.txt", BytesIO(b"data"), "text/plain")},
    )
    assert file_resp.status_code == 200
    file_id = file_resp.json()["id"]

    list_files = client.get(f"/files?thread={thread_id}", headers=headers)
    assert any(f["id"] == file_id for f in list_files.json())

    del_file = client.delete(f"/files/{file_id}", headers=headers)
    assert del_file.status_code == 200
    del_task = client.delete(f"/tasks/{task_id}", headers=headers)
    assert del_task.status_code == 200
