"""OpenTelemetry metrics setup and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from opentelemetry import metrics
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from app.core.config import Settings


@dataclass
class MetricsInstruments:
    workflow_latency_ms: Any
    workflow_requests: Any
    guardrail_rejections: Any
    llm_latency_ms: Any
    llm_tokens: Any


_meter_provider: Optional[MeterProvider] = None
_meter: Optional[Meter] = None
_metrics: Optional[MetricsInstruments] = None


def setup_metrics(settings: Settings) -> None:
    """Initialize the meter provider and core instruments."""

    global _meter_provider, _meter, _metrics

    if _meter_provider is not None:
        return

    resource = Resource.create({SERVICE_NAME: settings.otel_service_name})

    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPMetricExporter(
            endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
        )
    else:
        exporter = ConsoleMetricExporter()

    reader = PeriodicExportingMetricReader(exporter)
    _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(_meter_provider)

    _meter = metrics.get_meter("agentic-job-copilot")
    _metrics = MetricsInstruments(
        workflow_latency_ms=_meter.create_histogram(
            "workflow_latency_ms",
            unit="ms",
            description="End-to-end latency per workflow request",
        ),
        workflow_requests=_meter.create_counter(
            "workflow_requests_total",
            description="Total workflow requests handled",
        ),
        guardrail_rejections=_meter.create_counter(
            "guardrail_rejections_total",
            description="Count of chat prompts rejected by guardrails",
        ),
        llm_latency_ms=_meter.create_histogram(
            "llm_latency_ms",
            unit="ms",
            description="Latency for upstream LLM calls",
        ),
        llm_tokens=_meter.create_counter(
            "llm_tokens_total",
            description="Approximate tokens consumed per LLM call",
        ),
    )


def record_workflow_latency(workflow: str, duration_ms: float) -> None:
    if _metrics is None:
        return
    _metrics.workflow_latency_ms.record(
        max(duration_ms, 0.0), {"workflow": workflow}
    )


def increment_workflow_counter(workflow: str) -> None:
    if _metrics is None:
        return
    _metrics.workflow_requests.add(1, {"workflow": workflow})


def record_guardrail_rejection(reason: str) -> None:
    if _metrics is None:
        return
    _metrics.guardrail_rejections.add(1, {"reason": reason})


def record_llm_call(
    provider: str,
    model: str,
    duration_ms: float,
    *,
    tokens: Optional[int] = None,
    status: str = "success",
) -> None:
    if _metrics is None:
        return
    attributes = {"provider": provider, "model": model, "status": status}
    _metrics.llm_latency_ms.record(max(duration_ms, 0.0), attributes)
    if tokens is not None:
        _metrics.llm_tokens.add(max(tokens, 0), attributes)
