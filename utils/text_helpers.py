"""Utility helpers for AI text manipulation."""


def clean_ai_response(text: str) -> str:
    """Trim whitespace from AI responses."""
    return text.strip()


def truncate(text: str, max_length: int = 2000) -> str:
    """Truncate text for logging or previews."""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text
