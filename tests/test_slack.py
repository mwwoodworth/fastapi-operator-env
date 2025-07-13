import importlib
import os
import hmac
import hashlib
import time
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("TANA_API_KEY", "test")
os.environ.setdefault("VERCEL_TOKEN", "test")
os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")

os.environ["SLACK_SIGNING_SECRET"] = "secret"

import main as main_module

importlib.reload(main_module)
client = TestClient(main_module.app)

from codex.memory import agent_inbox


def _sign(body: str, ts: str) -> str:
    digest = hmac.new(
        os.environ["SLACK_SIGNING_SECRET"].encode(),
        f"v0:{ts}:{body}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"v0={digest}"


def test_slack_command_flow():
    item = agent_inbox.add_to_inbox("claude_prompt", {"prompt": "hi"}, "test")
    text = f"approve {item['task_id']}"
    body = f"text={text.replace(' ', '+')}"
    ts = str(int(time.time()))
    sig = _sign(body, ts)
    resp = client.post(
        "/webhook/slack/command",
        data={"text": text},
        headers={"X-Slack-Signature": sig, "X-Slack-Request-Timestamp": ts},
    )
    assert resp.status_code == 200
    assert "approved" in resp.json()["text"]

    text2 = f"status {item['task_id']}"
    body2 = f"text={text2.replace(' ', '+')}"
    ts2 = str(int(time.time()))
    sig2 = _sign(body2, ts2)
    resp2 = client.post(
        "/webhook/slack/command",
        data={"text": text2},
        headers={"X-Slack-Signature": sig2, "X-Slack-Request-Timestamp": ts2},
    )
    assert resp2.status_code == 200
    assert item["task_id"] in resp2.json()["text"]

    text3 = "query nothing"
    body3 = f"text={text3.replace(' ', '+')}"
    ts3 = str(int(time.time()))
    sig3 = _sign(body3, ts3)
    resp3 = client.post(
        "/webhook/slack/command",
        data={"text": text3},
        headers={"X-Slack-Signature": sig3, "X-Slack-Request-Timestamp": ts3},
    )
    assert resp3.status_code == 200
    text_resp = resp3.json()["text"]
    assert "No results" in text_resp or "not found" in text_resp
