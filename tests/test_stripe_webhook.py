import os
import importlib
import hmac
import hashlib
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("TANA_API_KEY", "test")
os.environ.setdefault("VERCEL_TOKEN", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")

import main as main_module
importlib.reload(main_module)
client = TestClient(main_module.app)

# ensure clean event log
Path("logs/stripe_events.json").unlink(missing_ok=True)

def _sign(payload: str, ts: str) -> str:
    digest = hmac.new(
        os.environ["STRIPE_WEBHOOK_SECRET"].encode(),
        f"{ts}.{payload}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"t={ts},v1={digest}"


def test_stripe_webhook_deduplication():
    event = {
        "id": "evt_test_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_email": "a@example.com",
                "description": "Pro Plan",
                "amount_total": 1000,
                "metadata": {"foo": "bar"},
            }
        },
    }
    payload = json.dumps(event)
    ts = str(int(time.time()))
    sig = _sign(payload, ts)
    resp = client.post(
        "/webhook/stripe",
        data=payload,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    # second delivery should be marked duplicate
    resp2 = client.post(
        "/webhook/stripe",
        data=payload,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"
