"""
Context propagation for distributed tracing.

Phase 3: Enhanced with OpenTelemetry context propagation for linking
HTTP requests to SDK calls (OpenAI, Anthropic, Google).
"""

import random
import string
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import Span

# Thread-local context for trace and span propagation
trace_context: ContextVar[Dict] = ContextVar("trace_context", default={})

# Phase 3: OpenTelemetry context for HTTP→SDK linking
_otel_request_context: ContextVar[Optional[Dict]] = ContextVar("otel_request_context", default=None)


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    ctx = trace_context.get()
    return ctx.get("trace_id")


def get_parent_span_id() -> Optional[str]:
    """Get parent span ID from context."""
    ctx = trace_context.get()
    span_stack = ctx.get("span_stack", [])
    return span_stack[-1] if span_stack else None


def new_span_id() -> str:
    """Generate new span ID (UUIDv4 for consistency)."""
    return str(uuid.uuid4())


def new_trace_id() -> str:
    """Generate new trace ID (UUID v4)."""
    return str(uuid.uuid4())


# ============================================================================
# Phase 3: OpenTelemetry Context Propagation
# ============================================================================


def set_otel_request_context(context_token: str, trace_id: str, span_id: str):
    """
    Set OpenTelemetry request context for HTTP→SDK span linking.

    Called by AutoTracerMiddleware to establish parent context for
    all SDK calls within the HTTP request.

    Args:
        context_token: Kalibr context token for chaining
        trace_id: OpenTelemetry trace ID (hex format)
        span_id: OpenTelemetry span ID (hex format)
    """
    _otel_request_context.set(
        {
            "context_token": context_token,
            "trace_id": trace_id,
            "span_id": span_id,
        }
    )


def get_otel_request_context() -> Optional[Dict]:
    """
    Get current OpenTelemetry request context.

    Returns:
        Dictionary with context_token, trace_id, span_id or None
    """
    return _otel_request_context.get()


def clear_otel_request_context():
    """Clear OpenTelemetry request context (called at end of request)"""
    _otel_request_context.set(None)


def get_current_otel_span() -> Optional[Span]:
    """
    Get the currently active OpenTelemetry span.

    Returns:
        Current span or None if no active span
    """
    return trace.get_current_span()


def get_otel_trace_context() -> Dict:
    """
    Get current OpenTelemetry trace context from active span.

    Returns:
        Dictionary with trace_id, span_id, or empty dict
    """
    span = get_current_otel_span()
    if span and span.get_span_context().is_valid:
        ctx = span.get_span_context()
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
            "is_valid": True,
        }
    return {}


def inject_kalibr_context_into_span(span: Span):
    """
    Inject Kalibr-specific context into OpenTelemetry span attributes.

    This links the OTel span back to Kalibr's context_token and HTTP trace.

    Args:
        span: OpenTelemetry span to annotate
    """
    ctx = get_otel_request_context()
    if ctx:
        if ctx.get("context_token"):
            span.set_attribute("kalibr.context_token", ctx["context_token"])
        if ctx.get("trace_id"):
            span.set_attribute("kalibr.http_trace_id", ctx["trace_id"])
        if ctx.get("span_id"):
            span.set_attribute("kalibr.http_span_id", ctx["span_id"])


# ============================================================================
# Goal Context for Outcome Tracking (v1.3.0)
# ============================================================================

_goal_context: ContextVar[Optional[str]] = ContextVar("goal_context", default=None)


def set_goal(goal: str):
    """Set the current goal for all subsequent Kalibr traces."""
    _goal_context.set(goal)


def get_goal() -> Optional[str]:
    """Get the current goal."""
    return _goal_context.get()


def clear_goal():
    """Clear the current goal."""
    _goal_context.set(None)


@contextmanager
def goal(goal_name: str):
    """Context manager to set goal for a block of code.

    Usage:
        with kalibr.goal("research_company"):
            agent.run("Research Weights & Biases")
    """
    previous = get_goal()
    set_goal(goal_name)
    try:
        yield
    finally:
        if previous:
            set_goal(previous)
        else:
            clear_goal()
