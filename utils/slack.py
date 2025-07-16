import json
import urllib.request

from core.settings import Settings

settings = Settings()


def send_slack_message(text: str) -> None:
    """Send a Slack message if SLACK_WEBHOOK_URL is configured."""
    url = settings.SLACK_WEBHOOK_URL
    if not url:
        return
    data = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass
