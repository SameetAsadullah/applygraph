"""OpenTelemetry bootstrap helpers."""
from __future__ import annotations

import contextlib
from typing import Iterator, Optional

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import Settings

_tracer_provider: Optional[TracerProvider] = None


def setup_tracing(app: FastAPI, settings: Settings) -> None:
    """Configure OpenTelemetry exporters and FastAPI instrumentation."""

    global _tracer_provider

    if _tracer_provider is not None:
        return

    resource = Resource.create({SERVICE_NAME: settings.otel_service_name})
    _tracer_provider = TracerProvider(resource=resource)

    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    else:
        exporter = ConsoleSpanExporter()

    _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(_tracer_provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()


def get_tracer():
    """Return the configured tracer."""

    return trace.get_tracer("agentic-job-copilot")


@contextlib.contextmanager
def workflow_span(name: str) -> Iterator[trace.Span]:
    """Convenience context manager for LangGraph nodes and tools."""

    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        yield span
