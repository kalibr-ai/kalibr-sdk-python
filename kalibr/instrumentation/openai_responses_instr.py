"""
OpenAI Responses API Instrumentation

Monkey-patches the OpenAI SDK to automatically emit OpenTelemetry spans
for all Responses API calls (client.responses.create and client.responses.stream).

Thread-safe singleton pattern using double-checked locking.
"""

import threading
import time
from functools import wraps
from typing import Any, Dict, Optional

from opentelemetry.trace import SpanKind

from .base import BaseCostAdapter, BaseInstrumentation


class OpenAIResponsesCostAdapter(BaseCostAdapter):
    """Cost calculation adapter for OpenAI Responses API.

    Uses centralized pricing from kalibr.pricing module.
    The Responses API uses the same models/pricing as Chat Completions.
    """

    def get_vendor_name(self) -> str:
        """Return vendor name for OpenAI."""
        return "openai"

    def calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Calculate cost in USD for an OpenAI Responses API call.

        Args:
            model: Model identifier (e.g., "gpt-4o", "gpt-4o-mini")
            usage: Token usage dict with input_tokens and output_tokens

        Returns:
            Cost in USD (rounded to 6 decimal places)
        """
        pricing = self.get_pricing_for_model(model)

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)


class OpenAIResponsesInstrumentation(BaseInstrumentation):
    """Instrumentation for OpenAI Responses API"""

    def __init__(self):
        super().__init__("kalibr.openai_responses")
        self._original_create = None
        self._original_async_create = None
        self.cost_adapter = OpenAIResponsesCostAdapter()

    def instrument(self) -> bool:
        """Apply monkey-patching to OpenAI Responses API"""
        if self._is_instrumented:
            return True

        try:
            import openai
            from openai.resources import responses as responses_mod

            # Patch sync create method
            if hasattr(responses_mod, "Responses") and hasattr(responses_mod.Responses, "create"):
                self._original_create = responses_mod.Responses.create
                responses_mod.Responses.create = self._traced_create_wrapper(
                    responses_mod.Responses.create
                )

            # Patch async create method
            if hasattr(responses_mod, "AsyncResponses") and hasattr(responses_mod.AsyncResponses, "create"):
                self._original_async_create = responses_mod.AsyncResponses.create
                responses_mod.AsyncResponses.create = self._traced_async_create_wrapper(
                    responses_mod.AsyncResponses.create
                )

            self._is_instrumented = True
            return True

        except (ImportError, AttributeError):
            # OpenAI SDK not installed or version doesn't have Responses API
            return False
        except Exception as e:
            print(f"❌ Failed to instrument OpenAI Responses API: {e}")
            return False

    def uninstrument(self) -> bool:
        """Remove monkey-patching from OpenAI Responses API"""
        if not self._is_instrumented:
            return True

        try:
            from openai.resources import responses as responses_mod

            if self._original_create and hasattr(responses_mod, "Responses"):
                responses_mod.Responses.create = self._original_create

            if self._original_async_create and hasattr(responses_mod, "AsyncResponses"):
                responses_mod.AsyncResponses.create = self._original_async_create

            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"❌ Failed to uninstrument OpenAI Responses API: {e}")
            return False

    def _traced_create_wrapper(self, original_func):
        """Wrapper for sync create method"""

        @wraps(original_func)
        def wrapper(self_instance, *args, **kwargs):
            model = kwargs.get("model", "unknown")

            with self.tracer.start_as_current_span(
                "openai.responses.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "openai",
                    "llm.request.model": model,
                    "llm.system": "openai",
                    "llm.api": "responses",
                },
            ) as span:
                start_time = time.time()

                try:
                    from kalibr.context import inject_kalibr_context_into_span
                    inject_kalibr_context_into_span(span)
                except Exception:
                    pass

                try:
                    result = original_func(self_instance, *args, **kwargs)
                    self._set_response_attributes(span, result, start_time)
                    return result
                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _traced_async_create_wrapper(self, original_func):
        """Wrapper for async create method"""

        @wraps(original_func)
        async def wrapper(self_instance, *args, **kwargs):
            model = kwargs.get("model", "unknown")

            with self.tracer.start_as_current_span(
                "openai.responses.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "openai",
                    "llm.request.model": model,
                    "llm.system": "openai",
                    "llm.api": "responses",
                },
            ) as span:
                start_time = time.time()

                try:
                    from kalibr.context import inject_kalibr_context_into_span
                    inject_kalibr_context_into_span(span)
                except Exception:
                    pass

                try:
                    result = await original_func(self_instance, *args, **kwargs)
                    self._set_response_attributes(span, result, start_time)
                    return result
                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _set_response_attributes(self, span, result, start_time: float) -> None:
        """Extract metadata from Responses API result and set span attributes"""
        try:
            # Model
            if hasattr(result, "model"):
                span.set_attribute("llm.response.model", result.model)

            # Token usage - Responses API uses usage.input_tokens / output_tokens
            if hasattr(result, "usage") and result.usage:
                usage = result.usage
                if hasattr(usage, "input_tokens"):
                    span.set_attribute("llm.usage.input_tokens", usage.input_tokens)
                    span.set_attribute("llm.usage.prompt_tokens", usage.input_tokens)
                if hasattr(usage, "output_tokens"):
                    span.set_attribute("llm.usage.output_tokens", usage.output_tokens)
                    span.set_attribute("llm.usage.completion_tokens", usage.output_tokens)

                total = getattr(usage, "total_tokens", None)
                if total is None:
                    total = getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)
                span.set_attribute("llm.usage.total_tokens", total)

                # Calculate cost
                cost = self.cost_adapter.calculate_cost(
                    getattr(result, "model", "unknown"),
                    {
                        "input_tokens": getattr(usage, "input_tokens", 0),
                        "output_tokens": getattr(usage, "output_tokens", 0),
                    },
                )
                span.set_attribute("llm.cost_usd", cost)

            # Latency
            latency_ms = (time.time() - start_time) * 1000
            span.set_attribute("llm.latency_ms", round(latency_ms, 2))

            # Response ID
            if hasattr(result, "id"):
                span.set_attribute("llm.response.id", result.id)

        except Exception as e:
            span.set_attribute("llm.metadata_extraction_error", str(e))


# Singleton instance
_responses_instrumentation = None
_responses_lock = threading.Lock()


def get_instrumentation() -> OpenAIResponsesInstrumentation:
    """Get or create the OpenAI Responses instrumentation singleton.

    Thread-safe singleton pattern using double-checked locking.
    """
    global _responses_instrumentation
    if _responses_instrumentation is None:
        with _responses_lock:
            if _responses_instrumentation is None:
                _responses_instrumentation = OpenAIResponsesInstrumentation()
    return _responses_instrumentation


def instrument() -> bool:
    """Instrument OpenAI Responses API"""
    return get_instrumentation().instrument()


def uninstrument() -> bool:
    """Uninstrument OpenAI Responses API"""
    return get_instrumentation().uninstrument()
