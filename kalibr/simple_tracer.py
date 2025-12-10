"""Simplified Kalibr tracer with direct event emission and capsule support.

Usage:
    from kalibr.simple_tracer import trace

    @trace(operation="summarize", provider="openai", model="gpt-4o")
    def my_function(text):
        return call_llm(text)

Capsule Usage (automatic when middleware is active):
    from fastapi import FastAPI, Request
    from kalibr.capsule_middleware import add_capsule_middleware
    from kalibr import trace

    app = FastAPI()
    add_capsule_middleware(app)

    @trace(operation="chat", provider="openai", model="gpt-4o")
    def process_request(request: Request, prompt: str):
        # Capsule automatically updated with this hop
        return llm_call(prompt)
"""

import json
import os
import random
import string
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Optional

try:
    import requests
except ImportError:
    print("[Kalibr SDK] ⚠️  requests not installed, install with: pip install requests")
    requests = None


def generate_span_id() -> str:
    """Generate UUIDv4 span ID for consistency."""
    return str(uuid.uuid4())


def send_event(payload: dict):
    """Send event directly to collector.

    Args:
        payload: Event data dict
    """
    if not requests:
        print("[Kalibr SDK] ❌ requests library not available")
        return

    url = os.getenv("KALIBR_COLLECTOR_URL", "https://api.kalibr.systems/api/ingest")
    api_key = os.getenv("KALIBR_API_KEY")
    if not api_key:
        print("[Kalibr SDK] ⚠️  KALIBR_API_KEY not set, traces will not be sent")
        return

    format_pref = os.getenv("KALIBR_COLLECTOR_FORMAT", "ndjson").lower()
    use_json_envelope = format_pref == "json"

    headers = {"X-API-Key": api_key}
    if use_json_envelope:
        headers["Content-Type"] = "application/json"
        body_cfg = {"events": [payload]}
    else:
        headers["Content-Type"] = "application/x-ndjson"
        body_cfg = "\n".join(json.dumps(evt) for evt in [payload]) + "\n"

    try:
        if use_json_envelope:
            response = requests.post(url, headers=headers, json=body_cfg, timeout=30)
        else:
            response = requests.post(url, headers=headers, data=body_cfg, timeout=30)
        if not response.ok:
            print(
                f"[Kalibr SDK] ❌ Collector rejected event: {response.status_code} - {response.text}"
            )
        else:
            duration_ms = payload.get("duration_ms") or payload.get("latency_ms") or 0
            total_cost = payload.get("total_cost_usd") or payload.get("cost_usd") or 0.0
            print(
                f"[Kalibr SDK] ✅ Event sent: {payload.get('operation','event')} ({duration_ms}ms, ${total_cost:.6f})"
            )
    except Exception as e:
        print(f"[Kalibr SDK] ❌ Failed to send event: {e}")


def trace(
    operation: str, provider: str, model: str, input_tokens: int = None, output_tokens: int = None
):
    """Decorator to trace function calls with full telemetry.

    Captures:
    - Duration (ms)
    - Tokens (estimated if not provided)
    - Cost (USD)
    - Errors
    - Runtime metadata

    Args:
        operation: Operation type (e.g., "summarize", "refine", "analyze")
        provider: LLM provider (e.g., "openai", "anthropic", "google")
        model: Model name (e.g., "gpt-4o", "claude-3-sonnet")
        input_tokens: Input token count (optional, will estimate)
        output_tokens: Output token count (optional, will estimate)

    Example:
        @trace(operation="summarize", provider="openai", model="gpt-4o")
        def summarize_text(text: str) -> str:
            return openai.chat.completions.create(...)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate IDs
            trace_id = str(uuid.uuid4())
            span_id = generate_span_id()  # Base62, 16 chars
            parent_span_id = kwargs.pop("parent_span_id", None)  # None or base62 string

            # Load environment config
            tenant_id = os.getenv("KALIBR_TENANT_ID", "default")
            workflow_id = os.getenv("KALIBR_WORKFLOW_ID", "multi_agent_demo")
            sandbox_id = os.getenv("SANDBOX_ID", "vercel_vm_001")
            runtime_env = os.getenv("RUNTIME_ENV", "vercel_vm")

            # Start timing
            start_time = time.time()

            # Execute function
            result = None
            status = "success"
            error_type = None
            error_message = None
            exception_to_raise = None

            try:
                result = func(*args, **kwargs)
            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                error_message = str(e)
                exception_to_raise = e
                print(f"[Kalibr SDK] ⚠️  Error in {func.__name__}: {error_type} - {error_message}")

            # End timing
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)

            # Token estimation
            actual_input_tokens = input_tokens or kwargs.get("input_tokens", 1000)
            actual_output_tokens = output_tokens or kwargs.get("output_tokens", 500)

            # Cost calculation (simplified pricing)
            # OpenAI GPT-4o: ~$2.50/1M input, ~$10/1M output
            # Anthropic Claude-3-Sonnet: ~$3/1M input, ~$15/1M output
            pricing_map = {
                "openai": {"gpt-4o": 0.00000250, "gpt-4": 0.00003000},
                "anthropic": {"claude-3-sonnet": 0.00000300, "claude-3-opus": 0.00001500},
                "google": {"gemini-pro": 0.00000125},
            }

            # Get unit price
            provider_pricing = pricing_map.get(provider, {})
            unit_price_usd = provider_pricing.get(model, 0.00002000)  # Default $0.02/1M

            # Calculate total cost
            total_cost_usd = (actual_input_tokens + actual_output_tokens) * unit_price_usd

            # Build payload
            payload = {
                "schema_version": "1.0",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,  # Note: parent_id not parent_span_id
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
                "sandbox_id": sandbox_id,
                "runtime_env": runtime_env,
                "provider": provider,
                "model_name": model,
                "model_id": model,  # For backward compatibility
                "operation": operation,
                "endpoint": func.__name__,
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
                "duration_ms": duration_ms,
                "latency_ms": duration_ms,  # For backward compatibility
                "unit_price_usd": unit_price_usd,
                "total_cost_usd": round(total_cost_usd, 6),
                "cost_usd": round(total_cost_usd, 6),  # For backward compatibility
                "status": status,
                "error_type": error_type,
                "error_message": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ts_start": datetime.now(timezone.utc).isoformat(),
                "ts_end": datetime.now(timezone.utc).isoformat(),
                "environment": os.getenv("KALIBR_ENVIRONMENT", "prod"),
                "service": os.getenv("KALIBR_SERVICE", "kalibr-app"),
                "vendor": provider,  # v0.2 compatibility
                "data_class": "economic",
            }

            # Send event to collector
            send_event(payload)

            # ========================================================================
            # PHASE 6: Append hop to capsule if available (from middleware)
            # ========================================================================
            try:
                # Check if we're in a FastAPI context with capsule middleware
                from starlette.requests import Request

                # Try to get capsule from request context (if available)
                capsule = kwargs.get("__kalibr_capsule")

                if capsule:
                    # Create hop from trace data
                    hop = {
                        "provider": provider,
                        "operation": operation,
                        "model": model,
                        "duration_ms": duration_ms,
                        "status": status,
                        "cost_usd": round(total_cost_usd, 6),
                        "input_tokens": actual_input_tokens,
                        "output_tokens": actual_output_tokens,
                    }

                    if error_type:
                        hop["error_type"] = error_type

                    # Add agent name if available
                    agent_name = os.getenv("KALIBR_AGENT_NAME", func.__name__)
                    hop["agent_name"] = agent_name

                    capsule.append_hop(hop)
                    print(
                        f"[Kalibr SDK] 📦 Appended hop to capsule: {operation} ({provider}/{model})"
                    )
            except Exception as e:
                # Capsule update is non-critical, just log
                print(f"[Kalibr SDK] ⚠️  Could not update capsule: {e}")
            # ========================================================================

            # Re-raise exception if there was one
            if exception_to_raise:
                raise exception_to_raise

            return result

        return wrapper

    return decorator
