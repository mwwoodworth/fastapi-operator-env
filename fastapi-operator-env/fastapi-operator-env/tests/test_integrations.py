import os
import importlib
import pytest

os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("TANA_API_KEY", "test")
os.environ.setdefault("VERCEL_TOKEN", "test")

import codex.integrations.clickup as clickup
import codex.integrations.notion as notion


def test_clickup_crud(httpx_mock):
    httpx_mock.add_response(json={"id": "1"})
    resp = clickup.create_task("ws", "tok", "123", "t", "d", idempotency_key="abc")
    req = httpx_mock.get_requests()[-1]
    assert req.headers["Authorization"] == "tok"
    assert req.headers["Idempotency-Key"] == "abc"
    assert resp["id"] == "1"

    httpx_mock.add_response(json={"id": "1"})
    resp = clickup.get_task("ws", "tok", "1")
    assert resp["id"] == "1"

    httpx_mock.add_response(json={"status": "ok"})
    resp = clickup.update_task("ws", "tok", "1", {"name": "new"}, idempotency_key="def")
    req = httpx_mock.get_requests()[-1]
    assert req.headers["Idempotency-Key"] == "def"
    assert resp["status"] == "ok"

    httpx_mock.add_response(json={"status": "deleted"})
    resp = clickup.delete_task("ws", "tok", "1")
    assert resp["status"] == "deleted"


def test_notion_crud(httpx_mock):
    httpx_mock.add_response(json={"id": "p"})
    resp = notion.create_page("ws", "token", "parent", "title")
    req = httpx_mock.get_requests()[-1]
    assert req.headers["Authorization"] == "Bearer token"
    assert resp["id"] == "p"

    httpx_mock.add_response(json={"id": "p"})
    assert notion.get_page("ws", "token", "p")["id"] == "p"

    httpx_mock.add_response(json={"archived": True})
    resp = notion.delete_page("ws", "token", "p")
    assert resp["archived"] is True
