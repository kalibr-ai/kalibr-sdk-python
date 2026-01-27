"""Centralized trace management and event creation.

This module handles:
- Trace lifecycle management
- Span creation and context propagation
- Event standardization to schema v1.0
- Error capturing with stack traces
"""

import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .context import get_trace_id, new_span_id, trace_context
from .cost_adapter import CostAdapterFactory


class Tracer:
    """Centralized tracer for creating and managing trace events."""

    def __init__(
        self,
        tenant_id: str = "default",
        environment: str = "prod",
        service: str = "kalibr-app",
        workflow_id: str = "default-workflow",
        workflow_version: str = "1.0",
        sandbox_id: str = "local",
        runtime_env: str = "local",
        parent_trace_id: Optional[str] = None,
    ):
        """Initialize tracer.

        Args:
            tenant_id: Tenant identifier
            environment: Environment (prod/staging/dev)
            service: Service name
            workflow_id: Workflow identifier
            workflow_version: Workflow version for A/B testing
            sandbox_id: Sandbox/VM identifier
            runtime_env: Runtime environment
            parent_trace_id: Parent trace ID for nested workflows
        """
        self.tenant_id = tenant_id
        self.environment = environment
        self.service = service
        self.workflow_id = workflow_id
        self.workflow_version = workflow_version
        self.sandbox_id = sandbox_id
        self.runtime_env = runtime_env
        self.parent_trace_id = parent_trace_id

    def create_span(
        self,
        operation: str,
        vendor: str = "unknown",
        model_name: str = "unknown",
        endpoint: Optional[str] = None,
    ) -> "SpanContext":
        """Create a new span context.

        Args:
            operation: Operation type (chat_completion, embedding, etc.)
            vendor: Vendor name (openai, anthropic, etc.)
            model_name: Model identifier
            endpoint: API endpoint or function name

        Returns:
            SpanContext instance for managing span lifecycle
        """
        # Get or create trace ID
        trace_id = get_trace_id()
        if not trace_id:
            trace_id = str(uuid.uuid4())

        # Create span ID
        span_id = new_span_id()

        # Get parent span ID from context
        ctx = trace_context.get()
        span_stack = ctx.get("span_stack", [])
        parent_id = span_stack[-1] if span_stack else None

        # Push span to stack
        ctx["trace_id"] = trace_id
        if "span_stack" not in ctx:
            ctx["span_stack"] = []
        ctx["span_stack"].append(span_id)
        trace_context.set(ctx)

        return SpanContext(
            tracer=self,
            trace_id=trace_id,
            span_id=span_id,
            parent_id=parent_id,
            operation=operation,
            vendor=vendor,
            model_name=model_name,
            endpoint=endpoint or operation,
        )

    def create_event(
        self,
        trace_id: str,
        span_id: str,
        parent_id: Optional[str],
        operation: str,
        vendor: str,
        model_name: str,
        endpoint: str,
        timestamp: datetime,
        latency_ms: int,
        status: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create standardized trace event matching schema v1.0 with billing fields.

        Args:
            trace_id: Trace identifier
            span_id: Span identifier
            parent_id: Parent span ID (None for root)
            operation: Operation type
            vendor: Vendor name
            model_name: Model identifier
            endpoint: API endpoint or function name
            timestamp: Event timestamp
            latency_ms: Duration in milliseconds
            status: Status (success/error)
            tokens_in: Input token count
            tokens_out: Output token count
            error_type: Error type if status=error
            error_message: Error message if status=error
            metadata: Additional metadata

        Returns:
            Standardized event dict with billing attribution
        """
        # Compute cost using adapter
        cost_adapter_result = CostAdapterFactory.compute_cost(
            vendor=vendor, model_name=model_name, tokens_in=tokens_in, tokens_out=tokens_out
        )

        # Calculate unit price (approximate)
        total_tokens = tokens_in + tokens_out
        unit_price_usd = cost_adapter_result / total_tokens if total_tokens > 0 else 0.0

        # Classify data tier
        if cost_adapter_result > 0 or tokens_in > 0:
            data_class = "economic"
        elif error_type:
            data_class = "system"
        else:
            data_class = "economic"

        event = {
            "schema_version": "1.0",  # Required by validator (legacy)
            "data_class": data_class,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_id": parent_id,
            "timestamp": timestamp.isoformat(),
            "ts_start": timestamp.isoformat(),  # For backward compatibility
            "ts_end": timestamp.isoformat(),  # For backward compatibility
            "endpoint": endpoint,
            "service": self.service,
            "vendor": vendor,
            "operation": operation,
            "cost_usd": cost_adapter_result,
            "latency_ms": latency_ms,
            "duration_ms": latency_ms,  # For backward compatibility
            "status": status,
            # Billing & Attribution
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "sandbox_id": self.sandbox_id,
            "runtime_env": self.runtime_env,
            # Workflow Context (NEW)
            "parent_trace_id": self.parent_trace_id,
            "workflow_version": self.workflow_version,
            # Model details
            "provider": vendor,  # Same as vendor for compatibility
            "model_id": model_name,  # For backward compatibility
            "model_name": model_name,
            # Token usage
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            # Cost breakdown
            "unit_price_usd": unit_price_usd,
            "total_cost_usd": cost_adapter_result,
            "execution_cost_usd": 0.0,  # Infrastructure cost (enriched by collector)
            "kalibr_fee_usd": 0.0,  # Platform fee (enriched by collector)
            # Error tracking
            "error_type": error_type,
            "error_message": error_message,
            "error_class": None,  # Enriched by collector
            # Reliability Metrics (NEW)
            "retry_count": metadata.get("retry_count", 0) if metadata else 0,
            "queue_latency_ms": metadata.get("queue_latency_ms") if metadata else None,
            "cold_start": metadata.get("cold_start", False) if metadata else False,
            # Metadata
            "metadata": {
                "environment": self.environment,
                "endpoint": endpoint,
                **(metadata or {}),
            },
        }

        return event

    def pop_span(self):
        """Pop current span from context stack."""
        ctx = trace_context.get()
        if ctx.get("span_stack"):
            ctx["span_stack"].pop()
        trace_context.set(ctx)


class SpanContext:
    """Context manager for span lifecycle."""

    def __init__(
        self,
        tracer: Tracer,
        trace_id: str,
        span_id: str,
        parent_id: Optional[str],
        operation: str,
        vendor: str,
        model_name: str,
        endpoint: str,
    ):
        self.tracer = tracer
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.operation = operation
        self.vendor = vendor
        self.model_name = model_name
        self.endpoint = endpoint

        self.ts_start: Optional[datetime] = None
        self.ts_end: Optional[datetime] = None
        self.tokens_in: int = 0
        self.tokens_out: int = 0
        self.status: str = "success"
        self.error_type: Optional[str] = None
        self.error_message: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

        # NEW: Reliability metrics
        self.retry_count: int = 0
        self.queue_latency_ms: Optional[int] = None
        self.cold_start: bool = False

    def __enter__(self):
        """Start span."""
        self.ts_start = datetime.now(timezone.utc)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End span and create event."""
        self.ts_end = datetime.now(timezone.utc)

        # Calculate duration
        latency_ms = int((self.ts_end - self.ts_start).total_seconds() * 1000)

        # Handle errors
        if exc_type is not None:
            self.status = "error"
            self.error_type = exc_type.__name__
            self.error_message = str(exc_val)

            # Capture stack trace
            tb_lines = traceback.format_exception(exc_type, exc_val, exc_tb)
            self.metadata["stack_trace"] = "".join(tb_lines)

        # Create event
        event = self.tracer.create_event(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_id=self.parent_id,
            operation=self.operation,
            vendor=self.vendor,
            model_name=self.model_name,
            endpoint=self.endpoint,
            timestamp=self.ts_start,
            latency_ms=latency_ms,
            status=self.status,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            error_type=self.error_type,
            error_message=self.error_message,
            metadata=self.metadata,
        )

        # Store event in context for retrieval
        ctx = trace_context.get()
        if "events" not in ctx:
            ctx["events"] = []
        ctx["events"].append(event)
        trace_context.set(ctx)

        # Pop span from stack
        self.tracer.pop_span()

        # Don't suppress exceptions
        return False

    def set_tokens(self, tokens_in: int, tokens_out: int):
        """Set token counts for span."""
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out

    def add_metadata(self, key: str, value: Any):
        """Add metadata to span."""
        self.metadata[key] = value

    def set_reliability_metrics(
        self, retry_count: int = 0, queue_latency_ms: Optional[int] = None, cold_start: bool = False
    ):
        """Set reliability metrics for span.

        Args:
            retry_count: Number of retries attempted
            queue_latency_ms: Time spent in queue
            cold_start: Whether this was a cold start
        """
        self.retry_count = retry_count
        self.queue_latency_ms = queue_latency_ms
        self.cold_start = cold_start

        # Also add to metadata for persistence
        self.metadata["retry_count"] = retry_count
        if queue_latency_ms is not None:
            self.metadata["queue_latency_ms"] = queue_latency_ms
        self.metadata["cold_start"] = cold_start

    def set_error(self, error: Exception):
        """Mark span as error and capture details."""
        self.status = "error"
        self.error_message = str(error)

        # Capture error type
        if not hasattr(self, "error_type"):
            self.error_type = type(error).__name__

        # Capture stack trace
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        self.metadata["stack_trace"] = "".join(tb_lines)
