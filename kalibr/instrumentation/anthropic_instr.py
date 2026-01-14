"""
Anthropic SDK Instrumentation

Monkey-patches the Anthropic SDK to automatically emit OpenTelemetry spans
for all message API calls.
"""

import time
from functools import wraps
from typing import Any, Dict, Optional

from opentelemetry.trace import SpanKind

from .base import BaseCostAdapter, BaseInstrumentation


class AnthropicCostAdapter(BaseCostAdapter):
    """Cost calculation adapter for Anthropic models.
    
    Uses centralized pricing from kalibr.pricing module.
    """

    def get_vendor_name(self) -> str:
        """Return vendor name for Anthropic."""
        return "anthropic"

    def calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Calculate cost in USD for an Anthropic API call.
        
        Args:
            model: Model identifier (e.g., "claude-3-opus", "claude-3-5-sonnet-20240620")
            usage: Token usage dict with input_tokens and output_tokens
            
        Returns:
            Cost in USD (rounded to 6 decimal places)
        """
        # Get pricing from centralized module (handles normalization)
        pricing = self.get_pricing_for_model(model)

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)


class AnthropicInstrumentation(BaseInstrumentation):
    """Instrumentation for Anthropic SDK"""

    def __init__(self):
        super().__init__("kalibr.anthropic")
        self._original_create = None
        self._original_async_create = None
        self.cost_adapter = AnthropicCostAdapter()

    def instrument(self) -> bool:
        """Apply monkey-patching to Anthropic SDK"""
        if self._is_instrumented:
            return True

        try:
            import anthropic
            from anthropic.resources import messages

            # Patch sync method
            if hasattr(messages.Messages, "create"):
                self._original_create = messages.Messages.create
                messages.Messages.create = self._traced_create_wrapper(messages.Messages.create)

            # Patch async method
            if hasattr(messages.AsyncMessages, "create"):
                self._original_async_create = messages.AsyncMessages.create
                messages.AsyncMessages.create = self._traced_async_create_wrapper(
                    messages.AsyncMessages.create
                )

            self._is_instrumented = True
            return True

        except ImportError:
            print("⚠️  Anthropic SDK not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"❌ Failed to instrument Anthropic SDK: {e}")
            return False

    def uninstrument(self) -> bool:
        """Remove monkey-patching from Anthropic SDK"""
        if not self._is_instrumented:
            return True

        try:
            import anthropic
            from anthropic.resources import messages

            # Restore sync method
            if self._original_create:
                messages.Messages.create = self._original_create

            # Restore async method
            if self._original_async_create:
                messages.AsyncMessages.create = self._original_async_create

            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"❌ Failed to uninstrument Anthropic SDK: {e}")
            return False

    def _traced_create_wrapper(self, original_func):
        """Wrapper for sync create method"""

        @wraps(original_func)
        def wrapper(self_instance, *args, **kwargs):
            # Extract model from kwargs
            model = kwargs.get("model", "unknown")

            # Create span with initial attributes
            with self.tracer.start_as_current_span(
                "anthropic.messages.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "anthropic",
                    "llm.request.model": model,
                    "llm.system": "anthropic",
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
                "anthropic.messages.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "anthropic",
                    "llm.request.model": model,
                    "llm.system": "anthropic",
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
                if hasattr(usage, "input_tokens"):
                    span.set_attribute("llm.usage.input_tokens", usage.input_tokens)
                    span.set_attribute("llm.usage.prompt_tokens", usage.input_tokens)  # Alias
                if hasattr(usage, "output_tokens"):
                    span.set_attribute("llm.usage.output_tokens", usage.output_tokens)
                    span.set_attribute("llm.usage.completion_tokens", usage.output_tokens)  # Alias

                total_tokens = usage.input_tokens + usage.output_tokens
                span.set_attribute("llm.usage.total_tokens", total_tokens)

                # Calculate cost
                cost = self.cost_adapter.calculate_cost(
                    result.model,
                    {
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                    },
                )
                span.set_attribute("llm.cost_usd", cost)

            # Latency
            latency_ms = (time.time() - start_time) * 1000
            span.set_attribute("llm.latency_ms", round(latency_ms, 2))

            # Response ID
            if hasattr(result, "id"):
                span.set_attribute("llm.response.id", result.id)

            # Stop reason
            if hasattr(result, "stop_reason"):
                span.set_attribute("llm.response.stop_reason", result.stop_reason)

        except Exception as e:
            # Don't fail the call if metadata extraction fails
            span.set_attribute("llm.metadata_extraction_error", str(e))


# Singleton instance
_anthropic_instrumentation = None


def get_instrumentation() -> AnthropicInstrumentation:
    """Get or create the Anthropic instrumentation singleton"""
    global _anthropic_instrumentation
    if _anthropic_instrumentation is None:
        _anthropic_instrumentation = AnthropicInstrumentation()
    return _anthropic_instrumentation


def instrument() -> bool:
    """Instrument Anthropic SDK"""
    return get_instrumentation().instrument()


def uninstrument() -> bool:
    """Uninstrument Anthropic SDK"""
    return get_instrumentation().uninstrument()
