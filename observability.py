from __future__ import annotations

from fastapi import FastAPI
from typing import Optional

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from aws_xray_sdk.core import patch_all


def init_tracing(app: FastAPI, endpoint: Optional[str]) -> None:
    """Initialize OpenTelemetry tracing for the FastAPI app."""
    if not endpoint:
        return

    patch_all()  # instrument stdlib + http frameworks for AWS X-Ray

    resource = Resource.create({"service.name": "fastapi-operator"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
