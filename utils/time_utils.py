from __future__ import annotations

"""Utility helpers for timezone-aware timestamps."""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return the current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()
