"""
OpenTelemetry Collector Setup

Configures OpenTelemetry tracer provider with multiple exporters:
1. OTLP exporter for sending to OpenTelemetry collectors
2. Kalibr HTTP exporter for sending to Kalibr backend
3. File exporter for local JSONL fallback
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

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
from opentelemetry.trace import StatusCode

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


class KalibrHTTPSpanExporter(SpanExporter):
    """Export spans to Kalibr backend via HTTP POST"""

    DEFAULT_URL = "https://kalibr-backend.fly.dev/api/ingest"

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        """Initialize the Kalibr HTTP exporter.

        Args:
            url: Kalibr collector URL (default: from KALIBR_COLLECTOR_URL env var)
            api_key: API key (default: from KALIBR_API_KEY env var)
            tenant_id: Tenant ID (default: from KALIBR_TENANT_ID env var)
        """
        self.url = url or os.getenv("KALIBR_COLLECTOR_URL", self.DEFAULT_URL)
        self.api_key = api_key or os.getenv("KALIBR_API_KEY")
        self.tenant_id = tenant_id or os.getenv("KALIBR_TENANT_ID", "default")
        self.environment = os.getenv("KALIBR_ENVIRONMENT", "production")

    def export(self, spans) -> SpanExportResult:
        """Export spans to Kalibr backend"""
        if not self.api_key:
            print("[Kalibr SDK] ⚠️  KALIBR_API_KEY not set, spans will not be sent to backend")
            return SpanExportResult.SUCCESS

        try:
            events = [self._convert_span(span) for span in spans]

            headers = {
                "X-API-Key": self.api_key,
                "X-Tenant-ID": self.tenant_id,
                "Content-Type": "application/json",
            }

            payload = {"events": events}

            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=30,
            )

            if not response.ok:
                print(
                    f"[Kalibr SDK] ❌ Backend rejected spans: {response.status_code} - {response.text}"
                )
                return SpanExportResult.FAILURE

            return SpanExportResult.SUCCESS

        except Exception as e:
            print(f"[Kalibr SDK] ❌ Failed to export spans to backend: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self):
        """Shutdown the exporter"""
        pass

    def _nanos_to_iso(self, nanos: int) -> str:
        """Convert nanoseconds since epoch to ISO format timestamp"""
        if nanos is None:
            return datetime.now(timezone.utc).isoformat()
        seconds = nanos / 1_000_000_000
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt.isoformat()

    def _get_attr(self, span, *keys, default=None):
        """Get attribute value from span, trying multiple keys"""
        attrs = dict(span.attributes) if span.attributes else {}
        for key in keys:
            if key in attrs:
                return attrs[key]
        return default

    def _convert_span(self, span) -> dict:
        """Convert OTel span to Kalibr event format"""
        attrs = dict(span.attributes) if span.attributes else {}

        # Calculate duration from span times (nanoseconds to milliseconds)
        duration_ms = 0
        if span.start_time and span.end_time:
            duration_ms = int((span.end_time - span.start_time) / 1_000_000)

        # Determine status
        is_error = (
            hasattr(span.status, "status_code") and span.status.status_code == StatusCode.ERROR
        )
        status = "error" if is_error else "success"

        # Extract provider and model
        provider = self._get_attr(span, "llm.vendor", "llm.system", "gen_ai.system", default="")
        model_id = self._get_attr(
            span, "llm.request.model", "llm.response.model", "gen_ai.request.model", default=""
        )

        # Extract token counts
        input_tokens = self._get_attr(
            span, "llm.usage.prompt_tokens", "gen_ai.usage.prompt_tokens", default=0
        )
        output_tokens = self._get_attr(
            span, "llm.usage.completion_tokens", "gen_ai.usage.completion_tokens", default=0
        )
        total_tokens = self._get_attr(
            span, "llm.usage.total_tokens", "gen_ai.usage.total_tokens", default=0
        )

        # If total_tokens not provided, calculate it
        if not total_tokens and (input_tokens or output_tokens):
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        # Build event payload
        event = {
            "schema_version": "1.0",
            "trace_id": format(span.context.trace_id, "032x"),
            "span_id": format(span.context.span_id, "016x"),
            "parent_id": format(span.parent.span_id, "016x") if span.parent else None,
            "tenant_id": self.tenant_id,
            "provider": provider,
            "model_id": model_id,
            "model_name": model_id,
            "operation": span.name,
            "endpoint": span.name,
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "total_tokens": total_tokens or 0,
            "cost_usd": self._get_attr(span, "llm.cost_usd", "gen_ai.usage.cost", default=0.0),
            "latency_ms": self._get_attr(span, "llm.latency_ms", default=duration_ms),
            "duration_ms": duration_ms,
            "status": status,
            "error_type": self._get_attr(span, "error.type", default=None) if is_error else None,
            "error_message": (
                self._get_attr(span, "error.message", default=None) if is_error else None
            ),
            "timestamp": self._nanos_to_iso(span.end_time),
            "ts_start": self._nanos_to_iso(span.start_time),
            "ts_end": self._nanos_to_iso(span.end_time),
            "goal": self._get_attr(span, "kalibr.goal", default=""),
            "environment": self.environment,
        }

        return event


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

    # Add Kalibr HTTP exporter if API key is configured
    kalibr_api_key = os.getenv("KALIBR_API_KEY")
    if kalibr_api_key:
        try:
            kalibr_exporter = KalibrHTTPSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(kalibr_exporter))
            print(f"✅ Kalibr backend exporter configured: {kalibr_exporter.url}")
        except Exception as e:
            print(f"⚠️  Failed to configure Kalibr backend exporter: {e}")

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
