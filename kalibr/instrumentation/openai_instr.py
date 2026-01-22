"""
OpenAI SDK Instrumentation

Monkey-patches the OpenAI SDK to automatically emit OpenTelemetry spans
for all chat completion API calls.

Thread-safe singleton pattern using double-checked locking.
"""

import threading
import time
from functools import wraps
from typing import Any, Dict, Optional

from opentelemetry.trace import SpanKind

from .base import BaseCostAdapter, BaseInstrumentation


class OpenAICostAdapter(BaseCostAdapter):
    """Cost calculation adapter for OpenAI models.
    
    Uses centralized pricing from kalibr.pricing module.
    """

    def get_vendor_name(self) -> str:
        """Return vendor name for OpenAI."""
        return "openai"

    def calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Calculate cost in USD for an OpenAI API call.
        
        Args:
            model: Model identifier (e.g., "gpt-4o", "gpt-4o-2024-05-13")
            usage: Token usage dict with prompt_tokens and completion_tokens
            
        Returns:
            Cost in USD (rounded to 6 decimal places)
        """
        # Get pricing from centralized module (handles normalization)
        pricing = self.get_pricing_for_model(model)

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)


class OpenAIInstrumentation(BaseInstrumentation):
    """Instrumentation for OpenAI SDK"""

    def __init__(self):
        super().__init__("kalibr.openai")
        self._original_create = None
        self._original_async_create = None
        self.cost_adapter = OpenAICostAdapter()

    def instrument(self) -> bool:
        """Apply monkey-patching to OpenAI SDK"""
        if self._is_instrumented:
            return True

        try:
            import openai
            from openai.resources.chat import completions

            # Patch sync method
            if hasattr(completions.Completions, "create"):
                self._original_create = completions.Completions.create
                completions.Completions.create = self._traced_create_wrapper(
                    completions.Completions.create
                )

            # Patch async method
            if hasattr(completions.AsyncCompletions, "create"):
                self._original_async_create = completions.AsyncCompletions.create
                completions.AsyncCompletions.create = self._traced_async_create_wrapper(
                    completions.AsyncCompletions.create
                )

            self._is_instrumented = True
            return True

        except ImportError:
            print("⚠️  OpenAI SDK not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"❌ Failed to instrument OpenAI SDK: {e}")
            return False

    def uninstrument(self) -> bool:
        """Remove monkey-patching from OpenAI SDK"""
        if not self._is_instrumented:
            return True

        try:
            import openai
            from openai.resources.chat import completions

            # Restore sync method
            if self._original_create:
                completions.Completions.create = self._original_create

            # Restore async method
            if self._original_async_create:
                completions.AsyncCompletions.create = self._original_async_create

            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"❌ Failed to uninstrument OpenAI SDK: {e}")
            return False

    def _traced_create_wrapper(self, original_func):
        """Wrapper for sync create method"""

        @wraps(original_func)
        def wrapper(self_instance, *args, **kwargs):
            # Extract model from kwargs
            model = kwargs.get("model", "unknown")

            # Create span with initial attributes
            with self.tracer.start_as_current_span(
                "openai.chat.completions.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "openai",
                    "llm.request.model": model,
                    "llm.system": "openai",
                },
            ) as span:
                start_time = time.time()

                # Phase 3: Inject Kalibr context for HTTP→SDK linking
                try:
                    from kalibr.context import inject_kalibr_context_into_span

                    inject_kalibr_context_into_span(span)
                except Exception:
                    pass  # Fail silently if context not available

                try:
                    # Call original method
                    result = original_func(self_instance, *args, **kwargs)

                    # Extract and set response metadata
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
            # Extract model from kwargs
            model = kwargs.get("model", "unknown")

            # Create span with initial attributes
            with self.tracer.start_as_current_span(
                "openai.chat.completions.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "openai",
                    "llm.request.model": model,
                    "llm.system": "openai",
                },
            ) as span:
                start_time = time.time()

                # Phase 3: Inject Kalibr context for HTTP→SDK linking
                try:
                    from kalibr.context import inject_kalibr_context_into_span

                    inject_kalibr_context_into_span(span)
                except Exception:
                    pass  # Fail silently if context not available

                try:
                    # Call original async method
                    result = await original_func(self_instance, *args, **kwargs)

                    # Extract and set response metadata
                    self._set_response_attributes(span, result, start_time)

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _set_response_attributes(self, span, result, start_time: float) -> None:
        """Extract metadata from response and set span attributes"""
        try:
            # Model
            if hasattr(result, "model"):
                span.set_attribute("llm.response.model", result.model)

            # Token usage
            if hasattr(result, "usage") and result.usage:
                usage = result.usage
                if hasattr(usage, "prompt_tokens"):
                    span.set_attribute("llm.usage.prompt_tokens", usage.prompt_tokens)
                if hasattr(usage, "completion_tokens"):
                    span.set_attribute("llm.usage.completion_tokens", usage.completion_tokens)
                if hasattr(usage, "total_tokens"):
                    span.set_attribute("llm.usage.total_tokens", usage.total_tokens)

                # Calculate cost
                cost = self.cost_adapter.calculate_cost(
                    result.model,
                    {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
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
            # Don't fail the call if metadata extraction fails
            span.set_attribute("llm.metadata_extraction_error", str(e))


# Singleton instance
_openai_instrumentation = None
_openai_lock = threading.Lock()


def get_instrumentation() -> OpenAIInstrumentation:
    """Get or create the OpenAI instrumentation singleton.
    
    Thread-safe singleton pattern using double-checked locking.
    """
    global _openai_instrumentation
    if _openai_instrumentation is None:
        with _openai_lock:
            # Double-check inside lock to prevent race condition
            if _openai_instrumentation is None:
                _openai_instrumentation = OpenAIInstrumentation()
    return _openai_instrumentation


def instrument() -> bool:
    """Instrument OpenAI SDK"""
    return get_instrumentation().instrument()


def uninstrument() -> bool:
    """Uninstrument OpenAI SDK"""
    return get_instrumentation().uninstrument()
