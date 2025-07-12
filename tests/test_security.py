import os
import importlib
from fastapi.testclient import TestClient

os.environ.setdefault("VERCEL_TOKEN", "test")
os.environ.setdefault("FERNET_SECRET", "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=")
os.environ.setdefault("SUPABASE_URL", "http://example.com")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")
os.environ.setdefault("TANA_API_KEY", "test")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("OPENAI_API_KEY", "test")


import main as main_module
importlib.reload(main_module)
client = TestClient(main_module.app)


def test_csrf_and_refresh_flow():
    os.environ["BASIC_AUTH_USERS"] = '{"user":"pass"}'
    os.environ["ADMIN_USERS"] = "user"
    importlib.reload(main_module)
    c = TestClient(main_module.app)
    resp = c.post(
        "/auth/token",
        data={"username": "user", "password": "pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    csrf_token = resp.json()["csrf_token"]
    cookies = resp.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies

    resp2 = c.post("/protected-test", headers={"X-CSRF-Token": csrf_token})
    assert resp2.status_code == 200

    refresh_cookie = {"refresh_token": cookies.get("refresh_token")}
    resp3 = c.post("/auth/refresh", cookies=refresh_cookie)
    assert resp3.status_code == 200
    assert "csrf_token" in resp3.json()
    os.environ.pop("BASIC_AUTH_USERS")
    os.environ.pop("ADMIN_USERS")
    importlib.reload(main_module)


def test_rate_limit():
    for _ in range(100):
        r = client.get("/health")
        assert r.status_code == 200
    r = client.get("/health")
    assert r.status_code == 429

