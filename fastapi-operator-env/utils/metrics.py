from __future__ import annotations

"""Prometheus metrics used across the application."""

from prometheus_client import (
    Counter,
    Summary,
    Gauge,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

REGISTRY = CollectorRegistry()

TASKS_EXECUTED = Counter(
    "tasks_executed_total",
    "Total tasks executed",
    registry=REGISTRY,
)
TASKS_SUCCEEDED = Counter(
    "tasks_succeeded_total",
    "Tasks completed successfully",
    registry=REGISTRY,
)
TASKS_FAILED = Counter(
    "tasks_failed_total",
    "Tasks that resulted in error",
    registry=REGISTRY,
)
TASK_DURATION = Summary(
    "task_duration_seconds",
    "Duration of task execution",
    registry=REGISTRY,
)

OPENAI_API_CALLS = Counter(
    "openai_api_calls_total",
    "Calls to OpenAI APIs",
    registry=REGISTRY,
)
OPENAI_TOKENS = Counter(
    "openai_tokens_total",
    "Tokens returned from OpenAI",
    registry=REGISTRY,
)
CLAUDE_API_CALLS = Counter(
    "claude_api_calls_total",
    "Calls to Claude APIs",
    registry=REGISTRY,
)
CLAUDE_TOKENS = Counter(
    "claude_tokens_total",
    "Tokens returned from Claude APIs",
    registry=REGISTRY,
)

MEMORY_ENTRIES = Gauge(
    "memory_entries_total",
    "Total memory entries",
    registry=REGISTRY,
)

# HTTP server metrics
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
    registry=REGISTRY,
)
HTTP_EXCEPTIONS = Counter(
    "http_exceptions_total",
    "Total unhandled exceptions",
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION = Summary(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    registry=REGISTRY,
)


def record_http_request(method: str, path: str, status: int, duration: float) -> None:
    """Record an HTTP request for Prometheus metrics."""
    HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
    HTTP_REQUEST_DURATION.observe(duration)


def latest() -> bytes:
    """Return the latest Prometheus metrics payload."""
    return generate_latest(REGISTRY)
