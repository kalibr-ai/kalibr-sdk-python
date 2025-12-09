"""Kalibr TracingProcessor for OpenAI Agents SDK.

This module implements a TracingProcessor that captures telemetry from
OpenAI Agents and sends it to the Kalibr backend.
"""

import atexit
import os
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

import httpx

# Import Kalibr cost adapters
try:
    from kalibr.cost_adapter import CostAdapterFactory
except ImportError:
    CostAdapterFactory = None

# Import tiktoken for token counting fallback
try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


def _count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens for given text."""
    if not text:
        return 0

    if HAS_TIKTOKEN:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(str(text)))
        except Exception:
            pass

    return len(str(text)) // 4


class EventBatcher:
    """Batches events for efficient sending to backend."""

    _instances: Dict[str, "EventBatcher"] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        batch_size: int = 100,
        flush_interval: float = 2.0,
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._event_queue: queue.Queue = queue.Queue(maxsize=5000)
        self._client = httpx.Client(timeout=10.0)
        self._shutdown = False

        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        atexit.register(self.shutdown)

    @classmethod
    def get_instance(
        cls,
        endpoint: str,
        api_key: str,
        batch_size: int = 100,
        flush_interval: float = 2.0,
    ) -> "EventBatcher":
        """Get or create a shared EventBatcher instance."""
        key = f"{endpoint}:{api_key}"
        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = cls(
                    endpoint=endpoint,
                    api_key=api_key,
                    batch_size=batch_size,
                    flush_interval=flush_interval,
                )
            return cls._instances[key]

    def enqueue(self, event: Dict[str, Any]):
        """Add event to queue."""
        try:
            self._event_queue.put_nowait(event)
        except queue.Full:
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except:
                pass

    def _flush_loop(self):
        """Background thread to flush events."""
        batch = []
        last_flush = time.time()

        while not self._shutdown:
            try:
                try:
                    event = self._event_queue.get(timeout=0.1)
                    batch.append(event)
                except queue.Empty:
                    pass

                now = time.time()
                should_flush = (
                    len(batch) >= self.batch_size or
                    (batch and now - last_flush >= self.flush_interval)
                )

                if should_flush:
                    self._send_batch(batch)
                    batch = []
                    last_flush = now
            except Exception:
                pass

        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        """Send batch to backend."""
        if not batch:
            return

        try:
            payload = {"events": batch}
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            self._client.post(self.endpoint, json=payload, headers=headers)
        except Exception:
            pass

    def shutdown(self):
        """Shutdown batcher."""
        if self._shutdown:
            return
        self._shutdown = True
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)
        self._client.close()

    def flush(self):
        """Force flush pending events."""
        events = []
        while True:
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except queue.Empty:
                break
        if events:
            self._send_batch(events)


class KalibrTracingProcessor:
    """OpenAI Agents SDK TracingProcessor for Kalibr observability.

    This processor implements the TracingProcessor interface from OpenAI's
    Agents SDK and sends telemetry to the Kalibr backend.

    Args:
        api_key: Kalibr API key
        endpoint: Backend endpoint URL
        tenant_id: Tenant identifier
        environment: Environment (prod/staging/dev)
        service: Service name
        workflow_id: Workflow identifier
        capture_input: Whether to capture inputs (default: True)
        capture_output: Whether to capture outputs (default: True)

    Usage:
        from agents.tracing import add_trace_processor
        from kalibr_openai_agents import KalibrTracingProcessor

        processor = KalibrTracingProcessor(tenant_id="my-tenant")
        add_trace_processor(processor)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        tenant_id: Optional[str] = None,
        environment: Optional[str] = None,
        service: Optional[str] = None,
        workflow_id: Optional[str] = None,
        capture_input: bool = True,
        capture_output: bool = True,
    ):
        self.api_key = api_key or os.getenv("KALIBR_API_KEY", "")
        self.endpoint = endpoint or os.getenv(
            "KALIBR_ENDPOINT",
            os.getenv("KALIBR_API_ENDPOINT", "https://api.kalibr.systems/api/v1/traces")
        )
        self.tenant_id = tenant_id or os.getenv("KALIBR_TENANT_ID", "default")
        self.environment = environment or os.getenv("KALIBR_ENVIRONMENT", "prod")
        self.service = service or os.getenv("KALIBR_SERVICE", "openai-agents-app")
        self.workflow_id = workflow_id or os.getenv("KALIBR_WORKFLOW_ID", "default-workflow")
        self.capture_input = capture_input
        self.capture_output = capture_output

        # Get shared batcher
        self._batcher = EventBatcher.get_instance(
            endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # Track active traces for context
        self._active_traces: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def on_trace_start(self, trace: Any) -> None:
        """Called when a trace starts.

        Args:
            trace: The trace object with trace_id, workflow_name, etc.
        """
        try:
            trace_id = getattr(trace, "trace_id", str(uuid.uuid4()))
            workflow_name = getattr(trace, "workflow_name", "unknown")

            with self._lock:
                self._active_traces[trace_id] = {
                    "trace_id": trace_id,
                    "workflow_name": workflow_name,
                    "started_at": datetime.now(timezone.utc),
                    "spans": [],
                }
        except Exception:
            pass

    def on_trace_end(self, trace: Any) -> None:
        """Called when a trace ends.

        Args:
            trace: The completed trace object
        """
        try:
            trace_id = getattr(trace, "trace_id", None)
            if not trace_id:
                return

            with self._lock:
                trace_data = self._active_traces.pop(trace_id, None)

            if not trace_data:
                return

            ended_at = datetime.now(timezone.utc)
            started_at = trace_data.get("started_at", ended_at)
            duration_ms = int((ended_at - started_at).total_seconds() * 1000)

            # Create trace-level event
            event = {
                "schema_version": "1.0",
                "trace_id": trace_id,
                "span_id": str(uuid.uuid4()),
                "parent_span_id": None,
                "tenant_id": self.tenant_id,
                "workflow_id": self.workflow_id,
                "provider": "openai",
                "model_id": "agents",
                "model_name": trace_data.get("workflow_name", "unknown"),
                "operation": f"trace:{trace_data.get('workflow_name', 'unknown')}",
                "endpoint": "agents.trace",
                "duration_ms": duration_ms,
                "latency_ms": duration_ms,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "total_cost_usd": 0.0,
                "status": "success",
                "timestamp": started_at.isoformat(),
                "ts_start": started_at.isoformat(),
                "ts_end": ended_at.isoformat(),
                "environment": self.environment,
                "service": self.service,
                "runtime_env": os.getenv("RUNTIME_ENV", "local"),
                "sandbox_id": os.getenv("SANDBOX_ID", "local"),
                "metadata": {
                    "span_type": "trace",
                    "openai_agents": True,
                    "workflow_name": trace_data.get("workflow_name"),
                    "span_count": len(trace_data.get("spans", [])),
                },
            }

            self._batcher.enqueue(event)

        except Exception:
            pass

    def on_span_start(self, span: Any) -> None:
        """Called when a span starts.

        Args:
            span: The span object with span_id, trace_id, span_data, etc.
        """
        # We process spans on end to have complete data
        pass

    def on_span_end(self, span: Any) -> None:
        """Called when a span ends.

        Args:
            span: The completed span object
        """
        try:
            self._process_span(span)
        except Exception:
            pass

    def _process_span(self, span: Any):
        """Process a completed span and create Kalibr event."""
        # Extract span attributes
        span_id = getattr(span, "span_id", str(uuid.uuid4()))
        trace_id = getattr(span, "trace_id", str(uuid.uuid4()))
        parent_id = getattr(span, "parent_id", None)

        # Get timing
        started_at = getattr(span, "started_at", None)
        ended_at = getattr(span, "ended_at", None)

        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        if isinstance(ended_at, str):
            ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))

        if not started_at:
            started_at = datetime.now(timezone.utc)
        if not ended_at:
            ended_at = datetime.now(timezone.utc)

        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        # Get span data
        span_data = getattr(span, "span_data", None)

        # Determine span type and extract relevant data
        span_type = "unknown"
        operation = "span"
        model = "unknown"
        input_tokens = 0
        output_tokens = 0
        input_preview = None
        output_preview = None

        if span_data is not None:
            span_type = type(span_data).__name__

            # Handle GenerationSpanData (LLM calls)
            if "Generation" in span_type:
                span_type = "generation"
                operation = "llm_generation"
                model = getattr(span_data, "model", "gpt-4")

                # Extract token counts from response
                response = getattr(span_data, "response", None)
                if response:
                    usage = getattr(response, "usage", None)
                    if usage:
                        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                        output_tokens = getattr(usage, "completion_tokens", 0) or 0

                # Extract input/output if capturing
                if self.capture_input:
                    input_data = getattr(span_data, "input", None)
                    if input_data:
                        input_preview = str(input_data)[:500]

                if self.capture_output:
                    output_data = getattr(span_data, "output", None)
                    if output_data:
                        output_preview = str(output_data)[:500]

            # Handle AgentSpanData
            elif "Agent" in span_type:
                span_type = "agent"
                agent_name = getattr(span_data, "name", "unknown")
                operation = f"agent:{agent_name}"

            # Handle FunctionSpanData (tool calls)
            elif "Function" in span_type:
                span_type = "function"
                func_name = getattr(span_data, "name", "unknown")
                operation = f"function:{func_name}"

                if self.capture_input:
                    input_data = getattr(span_data, "input", None)
                    if input_data:
                        input_preview = str(input_data)[:500]

                if self.capture_output:
                    output_data = getattr(span_data, "output", None)
                    if output_data:
                        output_preview = str(output_data)[:500]

            # Handle HandoffSpanData
            elif "Handoff" in span_type:
                span_type = "handoff"
                from_agent = getattr(span_data, "from_agent", "unknown")
                to_agent = getattr(span_data, "to_agent", "unknown")
                operation = f"handoff:{from_agent}->{to_agent}"

            # Handle GuardrailSpanData
            elif "Guardrail" in span_type:
                span_type = "guardrail"
                guardrail_name = getattr(span_data, "name", "unknown")
                operation = f"guardrail:{guardrail_name}"

            else:
                # Generic span
                operation = f"span:{span_type}"

        # Calculate cost for generation spans
        cost_usd = 0.0
        if span_type == "generation" and CostAdapterFactory is not None:
            cost_usd = CostAdapterFactory.compute_cost(
                vendor="openai",
                model_name=model,
                tokens_in=input_tokens,
                tokens_out=output_tokens,
            )

        # Get error info
        error = getattr(span, "error", None)
        status = "error" if error else "success"
        error_type = None
        error_message = None
        if error:
            error_type = type(error).__name__
            error_message = str(error)[:512]

        # Build event
        event = {
            "schema_version": "1.0",
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "provider": "openai",
            "model_id": model,
            "model_name": model,
            "operation": operation,
            "endpoint": f"agents.{span_type}",
            "duration_ms": duration_ms,
            "latency_ms": duration_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost_usd,
            "total_cost_usd": cost_usd,
            "status": status,
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": started_at.isoformat(),
            "ts_start": started_at.isoformat(),
            "ts_end": ended_at.isoformat(),
            "environment": self.environment,
            "service": self.service,
            "runtime_env": os.getenv("RUNTIME_ENV", "local"),
            "sandbox_id": os.getenv("SANDBOX_ID", "local"),
            "metadata": {
                "span_type": span_type,
                "openai_agents": True,
                "input_preview": input_preview,
                "output_preview": output_preview,
            },
        }

        self._batcher.enqueue(event)

    def shutdown(self) -> None:
        """Shutdown the processor and flush pending events."""
        self._batcher.shutdown()

    def force_flush(self) -> None:
        """Force flush all pending events."""
        self._batcher.flush()


def setup_kalibr_tracing(
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
    tenant_id: Optional[str] = None,
    environment: Optional[str] = None,
    service: Optional[str] = None,
    workflow_id: Optional[str] = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> KalibrTracingProcessor:
    """Set up Kalibr tracing for OpenAI Agents SDK.

    This is a convenience function that creates a KalibrTracingProcessor
    and adds it to the OpenAI Agents SDK's trace processors.

    Args:
        api_key: Kalibr API key
        endpoint: Backend endpoint URL
        tenant_id: Tenant identifier
        environment: Environment (prod/staging/dev)
        service: Service name
        workflow_id: Workflow identifier
        capture_input: Whether to capture inputs
        capture_output: Whether to capture outputs

    Returns:
        The configured KalibrTracingProcessor

    Usage:
        from kalibr_openai_agents import setup_kalibr_tracing

        # Quick setup
        processor = setup_kalibr_tracing(tenant_id="my-tenant")

        # Now use OpenAI Agents normally
    """
    processor = KalibrTracingProcessor(
        api_key=api_key,
        endpoint=endpoint,
        tenant_id=tenant_id,
        environment=environment,
        service=service,
        workflow_id=workflow_id,
        capture_input=capture_input,
        capture_output=capture_output,
    )

    # Try to add to OpenAI Agents SDK trace processors
    try:
        from agents.tracing import add_trace_processor
        add_trace_processor(processor)
    except ImportError:
        print("[Kalibr] OpenAI Agents SDK not installed, processor created but not registered")

    return processor
