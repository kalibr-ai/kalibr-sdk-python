"""
Auto-Tracer Middleware
Automatically traces all requests through Kalibr runtime
Phase 3B - Runtime Host Integration
Phase 3D - Capsule Auto-Emission
"""

import atexit
import json
import os
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AutoTracerMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically traces all requests.

    Features:
    - Captures every request/response
    - Generates trace events without @trace decorator
    - Batches events for efficient submission
    - Auto-flushes on shutdown
    - Context token propagation
    """

    def __init__(
        self,
        app,
        agent_name: str = "unknown",
        runtime_id: str = None,
        context_token: str = None,
        collector_url: str = None,
        api_key: str = None,
        tenant_id: str = None,
        max_events: int = 100,
        flush_interval: int = 30,
    ):
        super().__init__(app)

        # Runtime metadata
        self.agent_name = agent_name
        self.runtime_id = runtime_id or os.getenv("KALIBR_RUNTIME_ID", str(uuid.uuid4()))
        self.context_token = context_token or os.getenv("KALIBR_CONTEXT_TOKEN", str(uuid.uuid4()))

        # Collector config
        self.collector_url = collector_url or os.getenv(
            "KALIBR_COLLECTOR_URL", "https://api.kalibr.systems/api/ingest"
        )
        self.api_key = api_key or os.getenv("KALIBR_API_KEY", "")
        self.tenant_id = tenant_id or os.getenv("KALIBR_TENANT_ID", "default")

        # Buffering config
        self.max_events = int(os.getenv("KALIBR_MAX_EVENTS", max_events))
        self.flush_interval = int(os.getenv("KALIBR_FLUSH_INTERVAL", flush_interval))

        # Event buffer
        self.events = queue.Queue()
        self.event_count = 0
        self.lock = threading.Lock()

        # Phase 3D: Capsule emission tracking
        self.capsule_events: List[Dict[str, Any]] = []
        self.total_cost = 0.0
        self.total_latency = 0
        self.last_capsule_emission = time.time()

        # Background flusher (handles both traces and capsules)
        self.flusher_thread = threading.Thread(target=self._background_flusher, daemon=True)
        self.flusher_thread.start()

        # Register shutdown handler
        atexit.register(self.flush_all)

        print(
            f"✅ AutoTracerMiddleware initialized: runtime_id={self.runtime_id}, context_token={self.context_token}"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Intercept and trace every request.
        Phase 3: Creates OpenTelemetry span for context propagation to SDK calls.
        """
        # Skip tracing for health/docs endpoints
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Generate trace metadata
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        start_time = time.time()
        ts_start = datetime.now(timezone.utc)

        # Extract parent context from headers (for chaining)
        parent_context_token = request.headers.get("X-Kalibr-Context-Token")
        parent_trace_id = request.headers.get("X-Kalibr-Trace-ID")

        # Phase 3: Create OpenTelemetry span for HTTP request
        # This enables SDK calls within the request to be linked as child spans
        from kalibr.context import clear_otel_request_context, set_otel_request_context
        from opentelemetry import trace as otel_trace

        tracer = otel_trace.get_tracer("kalibr.http")

        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            kind=otel_trace.SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.path": request.url.path,
                "kalibr.runtime_id": self.runtime_id,
                "kalibr.context_token": self.context_token,
                "kalibr.agent_name": self.agent_name,
            },
        ) as http_span:
            # Get OpenTelemetry trace/span IDs
            span_context = http_span.get_span_context()
            otel_trace_id = format(span_context.trace_id, "032x")
            otel_span_id = format(span_context.span_id, "016x")

            # Set context for SDK instrumentation to inherit
            set_otel_request_context(
                context_token=self.context_token, trace_id=otel_trace_id, span_id=otel_span_id
            )

            # Process request
            try:
                response = await call_next(request)
                status = "success"
                error_type = ""
                error_message = ""

                # Set HTTP span attributes
                http_span.set_attribute("http.status_code", response.status_code)

            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                error_message = str(e)

                # Set error on HTTP span
                http_span.set_status(otel_trace.Status(otel_trace.StatusCode.ERROR))
                http_span.set_attribute("error.type", error_type)
                http_span.set_attribute("error.message", error_message)
                http_span.record_exception(e)

                # Re-raise to not swallow exceptions
                raise
            finally:
                # Clear context at end of request
                clear_otel_request_context()
            # Calculate metrics
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            ts_end = datetime.now(timezone.utc)

            # Create trace event
            event = {
                "schema_version": "1.0",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_id": parent_trace_id or "",
                "tenant_id": self.tenant_id,
                "ts_start": ts_start.isoformat() + "Z",
                "ts_end": ts_end.isoformat() + "Z",
                "timestamp": ts_end.isoformat() + "Z",
                "environment": os.getenv("KALIBR_ENVIRONMENT", "production"),
                "runtime_env": "kalibr_auto_tracer",
                "provider": "runtime",
                "model_id": self.agent_name,
                "model_name": self.agent_name,
                "operation": request.method.lower(),
                "endpoint": request.url.path,
                "duration_ms": duration_ms,
                "latency_ms": duration_ms,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "cost_est_usd": 0.0,
                "status": status,
                "error_type": error_type,
                "error_message": error_message,
                # Phase 3 metadata
                "runtime_id": self.runtime_id,
                "context_token": self.context_token,
                "parent_context_token": parent_context_token or "",
            }

            # Add to buffer
            self.events.put(event)
            with self.lock:
                self.event_count += 1

                # Phase 3D: Add to capsule tracking
                self.capsule_events.append(
                    {
                        "trace_id": trace_id,
                        "operation": request.method.lower(),
                        "endpoint": request.url.path,
                        "duration_ms": duration_ms,
                        "cost_usd": event.get("cost_est_usd", 0.0),
                        "status": status,
                        "timestamp": ts_end.isoformat() + "Z",
                    }
                )
                self.total_cost += event.get("cost_est_usd", 0.0)
                self.total_latency += duration_ms

            # Check if flush needed
            if self.event_count >= self.max_events:
                threading.Thread(target=self.flush_all, daemon=True).start()

        return response

    def _background_flusher(self):
        """
        Background thread that flushes events and capsules periodically.
        Phase 3D: Dual trigger - interval OR count
        """
        while True:
            time.sleep(self.flush_interval)

            # Check if flush needed (interval OR count)
            should_flush = False
            with self.lock:
                time_since_last = time.time() - self.last_capsule_emission
                if time_since_last >= self.flush_interval or self.event_count >= self.max_events:
                    should_flush = True

            if should_flush:
                self.flush_all()

    def flush_events(self):
        """
        Flush buffered trace events to collector.
        """
        if self.event_count == 0:
            return

        with self.lock:
            events_to_send = []
            while not self.events.empty():
                try:
                    events_to_send.append(self.events.get_nowait())
                except queue.Empty:
                    break

            if not events_to_send:
                return

            # Send to collector
            try:
                # ✅ Fixed Bug 2: Send as JSON dict instead of NDJSON string
                # Backend expects: {"events": [event_dict]}
                payload = {"events": events_to_send}

                # Send to collector
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(
                        self.collector_url,
                        json=payload,  # ✅ Sends as JSON object, not string
                        headers={
                            "X-API-Key": self.api_key,
                            "Content-Type": "application/json",
                        },
                    )
                    response.raise_for_status()

                print(f"✅ Flushed {len(events_to_send)} trace events to collector")
                self.event_count = 0

            except Exception as e:
                print(f"⚠️ Failed to flush events: {e}")
                # Re-queue events for retry
                for event in events_to_send:
                    self.events.put(event)

    def emit_capsule(self):
        """
        Phase 3D: Emit accumulated traces as a capsule.
        Auto-posts to /api/ingest/capsule with aggregated metrics.
        """
        with self.lock:
            if not self.capsule_events:
                return

            # Build capsule payload
            capsule = {
                "trace_id": (
                    self.capsule_events[0]["trace_id"] if self.capsule_events else str(uuid.uuid4())
                ),
                "runtime_id": self.runtime_id,
                "agent_name": self.agent_name,
                "context_token": self.context_token,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "aggregate_cost_usd": round(self.total_cost, 6),
                "aggregate_latency_ms": self.total_latency,
                "last_n_hops": self.capsule_events[-5:],  # Last 5 hops
                "tenant_id": self.tenant_id,
                "metadata": {
                    "runtime_provider": "local",
                    "total_events": len(self.capsule_events),
                    "emission_reason": "auto_flush",
                },
            }

            # Reset capsule tracking
            events_count = len(self.capsule_events)
            self.capsule_events = []
            self.total_cost = 0.0
            self.total_latency = 0
            self.last_capsule_emission = time.time()

        # Send capsule to backend
        try:
            capsule_url = self.collector_url.replace("/api/ingest", "/api/ingest/capsule")

            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    capsule_url,
                    json=capsule,
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()

            print(
                f"📦 Emitted capsule: {events_count} events, cost=${capsule['aggregate_cost_usd']:.6f}, latency={capsule['aggregate_latency_ms']}ms"
            )

        except Exception as e:
            print(f"⚠️ Failed to emit capsule: {e}")

    def flush_all(self):
        """
        Phase 3D: Flush both trace events and emit capsule.
        Called on shutdown or when thresholds reached.
        """
        # Flush individual trace events first
        self.flush_events()

        # Then emit capsule
        self.emit_capsule()
