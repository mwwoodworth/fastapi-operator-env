import os
import time
import httpx

INTERVAL = 900  # 15 minutes
REPO = os.getenv("GITHUB_REPO", "mwwoodworth/fastapi-operator-env")
STATE_FILE = os.getenv("DEPLOY_HASH_FILE", "last_deploy_hash.txt")
WEBHOOK = os.getenv("DEPLOY_WEBHOOK", "http://localhost:10000/webhook/github")

def _get_latest_commit() -> str:
    url = f"https://api.github.com/repos/{REPO}/commits/main"
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json().get("sha", "")


def _load_last() -> str:
    if os.path.exists(STATE_FILE):
        return open(STATE_FILE).read().strip()
    return ""


def _save_last(sha: str) -> None:
    with open(STATE_FILE, "w") as f:
        f.write(sha)


def _trigger_deploy(sha: str) -> None:
    try:
        httpx.post(WEBHOOK, json={"sha": sha}, timeout=10)
    except Exception as exc:  # noqa: BLE001
        print(f"deploy webhook failed: {exc}")


def main() -> None:
    while True:
        try:
            latest = _get_latest_commit()
            last = _load_last()
            if latest and latest != last:
                _trigger_deploy(latest)
                _save_last(latest)
        except Exception as exc:  # noqa: BLE001
            print(f"deploy watcher error: {exc}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
