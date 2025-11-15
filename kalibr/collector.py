"""
OpenTelemetry Collector Setup

Configures OpenTelemetry tracer provider with multiple exporters:
1. OTLP exporter for sending to OpenTelemetry collectors
2. File exporter for local JSONL fallback
"""

import json
import os
from pathlib import Path
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
    SpanExportResult,
)

try:
    from opentelemetry.sdk.trace import ReadableSpan
except ImportError:
    ReadableSpan = None


class FileSpanExporter(SpanExporter):
    """Export spans to a JSONL file"""

    def __init__(self, file_path: str = "/tmp/kalibr_otel_spans.jsonl"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans) -> SpanExportResult:
        """Export spans to JSONL file"""
        try:
            with open(self.file_path, "a") as f:
                for span in spans:
                    span_dict = self._span_to_dict(span)
                    f.write(json.dumps(span_dict) + "\n")
            return SpanExportResult.SUCCESS
        except Exception as e:
            print(f"❌ Failed to export spans to file: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self):
        """Shutdown the exporter"""
        pass

    def _span_to_dict(self, span) -> dict:
        """Convert span to dictionary format"""
        return {
            "trace_id": format(span.context.trace_id, "032x"),
            "span_id": format(span.context.span_id, "016x"),
            "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
            "name": span.name,
            "kind": span.kind.name if hasattr(span.kind, "name") else str(span.kind),
            "start_time_unix_nano": span.start_time,
            "end_time_unix_nano": span.end_time,
            "attributes": dict(span.attributes) if span.attributes else {},
            "status": {
                "code": (
                    span.status.status_code.name
                    if hasattr(span.status.status_code, "name")
                    else str(span.status.status_code)
                ),
                "description": getattr(span.status, "description", ""),
            },
            "events": [
                {
                    "name": event.name,
                    "timestamp": event.timestamp,
                    "attributes": dict(event.attributes) if event.attributes else {},
                }
                for event in (span.events or [])
            ],
        }


_tracer_provider: Optional[TracerProvider] = None
_is_configured = False


def setup_collector(
    service_name: str = "kalibr",
    otlp_endpoint: Optional[str] = None,
    file_export: bool = True,
    console_export: bool = False,
) -> TracerProvider:
    """
    Setup OpenTelemetry collector with multiple exporters

    Args:
        service_name: Service name for the tracer provider
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
                       If None, reads from OTEL_EXPORTER_OTLP_ENDPOINT env var
        file_export: Whether to export spans to local JSONL file
        console_export: Whether to export spans to console (for debugging)

    Returns:
        Configured TracerProvider instance
    """
    global _tracer_provider, _is_configured

    if _is_configured and _tracer_provider:
        return _tracer_provider

    # Create resource with service name
    resource = Resource(attributes={SERVICE_NAME: service_name})

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter if endpoint is configured
    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            print(f"✅ OTLP exporter configured: {otlp_endpoint}")
        except Exception as e:
            print(f"⚠️  Failed to configure OTLP exporter: {e}")

    # Add file exporter for local fallback
    if file_export:
        try:
            file_exporter = FileSpanExporter("/tmp/kalibr_otel_spans.jsonl")
            provider.add_span_processor(BatchSpanProcessor(file_exporter))
            print("✅ File exporter configured: /tmp/kalibr_otel_spans.jsonl")
        except Exception as e:
            print(f"⚠️  Failed to configure file exporter: {e}")

    # Add console exporter for debugging
    if console_export:
        try:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
            print("✅ Console exporter configured")
        except Exception as e:
            print(f"⚠️  Failed to configure console exporter: {e}")

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    _tracer_provider = provider
    _is_configured = True

    return provider


def get_tracer_provider() -> Optional[TracerProvider]:
    """Get the current tracer provider"""
    return _tracer_provider


def is_configured() -> bool:
    """Check if collector is configured"""
    return _is_configured


def shutdown_collector():
    """Shutdown the tracer provider and flush all spans"""
    global _tracer_provider, _is_configured

    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None
        _is_configured = False
        print("✅ Tracer provider shutdown")
