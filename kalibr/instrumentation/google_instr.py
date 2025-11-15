"""
Google Generative AI SDK Instrumentation

Monkey-patches the Google Generative AI SDK to automatically emit OpenTelemetry spans
for all content generation API calls.
"""

import time
from functools import wraps
from typing import Any, Dict, Optional

from opentelemetry.trace import SpanKind

from .base import BaseCostAdapter, BaseInstrumentation


class GoogleCostAdapter(BaseCostAdapter):
    """Cost calculation adapter for Google Generative AI models"""

    # Pricing per 1K tokens (USD) - Updated November 2025
    PRICING = {
        # Gemini 2.5 models
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
        "gemini-2.5-flash": {"input": 0.000075, "output": 0.0003},
        # Gemini 2.0 models
        "gemini-2.0-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-2.0-flash-thinking": {"input": 0.000075, "output": 0.0003},
        # Gemini 1.5 models
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
        "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-1.5-flash-8b": {"input": 0.0000375, "output": 0.00015},
        # Gemini 1.0 models
        "gemini-1.0-pro": {"input": 0.0005, "output": 0.0015},
        "gemini-pro": {"input": 0.0005, "output": 0.0015},  # Alias
    }

    def calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Calculate cost in USD for a Google Generative AI API call"""
        # Normalize model name
        base_model = model.lower()

        # Try exact match first
        pricing = self.get_pricing(base_model)

        # Try fuzzy matching for versioned models
        if not pricing:
            for known_model in self.PRICING.keys():
                if known_model in base_model or base_model in known_model:
                    pricing = self.PRICING[known_model]
                    break

        if not pricing:
            # Default to Gemini 1.5 Pro pricing if unknown
            pricing = {"input": 0.00125, "output": 0.005}

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]

        return round(input_cost + output_cost, 6)


class GoogleInstrumentation(BaseInstrumentation):
    """Instrumentation for Google Generative AI SDK"""

    def __init__(self):
        super().__init__("kalibr.google")
        self._original_generate_content = None
        self._original_async_generate_content = None
        self.cost_adapter = GoogleCostAdapter()

    def instrument(self) -> bool:
        """Apply monkey-patching to Google Generative AI SDK"""
        if self._is_instrumented:
            return True

        try:
            import google.generativeai as genai
            from google.generativeai.generative_models import GenerativeModel

            # Patch sync method
            if hasattr(GenerativeModel, "generate_content"):
                self._original_generate_content = GenerativeModel.generate_content
                GenerativeModel.generate_content = self._traced_generate_wrapper(
                    GenerativeModel.generate_content
                )

            # Patch async method (if available)
            if hasattr(GenerativeModel, "generate_content_async"):
                self._original_async_generate_content = GenerativeModel.generate_content_async
                GenerativeModel.generate_content_async = self._traced_async_generate_wrapper(
                    GenerativeModel.generate_content_async
                )

            self._is_instrumented = True
            return True

        except ImportError:
            print("⚠️  Google Generative AI SDK not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"❌ Failed to instrument Google Generative AI SDK: {e}")
            return False

    def uninstrument(self) -> bool:
        """Remove monkey-patching from Google Generative AI SDK"""
        if not self._is_instrumented:
            return True

        try:
            import google.generativeai as genai
            from google.generativeai.generative_models import GenerativeModel

            # Restore sync method
            if self._original_generate_content:
                GenerativeModel.generate_content = self._original_generate_content

            # Restore async method
            if self._original_async_generate_content:
                GenerativeModel.generate_content_async = self._original_async_generate_content

            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"❌ Failed to uninstrument Google Generative AI SDK: {e}")
            return False

    def _traced_generate_wrapper(self, original_func):
        """Wrapper for sync generate_content method"""

        @wraps(original_func)
        def wrapper(self_instance, *args, **kwargs):
            # Extract model name from instance
            model = getattr(self_instance, "_model_name", "unknown")

            # Create span with initial attributes
            with self.tracer.start_as_current_span(
                "google.generativeai.generate_content",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "google",
                    "llm.request.model": model,
                    "llm.system": "google.generativeai",
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
                    self._set_response_attributes(span, result, model, start_time)

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _traced_async_generate_wrapper(self, original_func):
        """Wrapper for async generate_content method"""

        @wraps(original_func)
        async def wrapper(self_instance, *args, **kwargs):
            # Extract model name from instance
            model = getattr(self_instance, "_model_name", "unknown")

            # Create span with initial attributes
            with self.tracer.start_as_current_span(
                "google.generativeai.generate_content",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "google",
                    "llm.request.model": model,
                    "llm.system": "google.generativeai",
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
                    self._set_response_attributes(span, result, model, start_time)

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _set_response_attributes(self, span, result, model: str, start_time: float) -> None:
        """Extract metadata from response and set span attributes"""
        try:
            # Model (from instance)
            span.set_attribute("llm.response.model", model)

            # Token usage
            if hasattr(result, "usage_metadata") and result.usage_metadata:
                usage = result.usage_metadata

                prompt_tokens = getattr(usage, "prompt_token_count", 0)
                completion_tokens = getattr(usage, "candidates_token_count", 0)
                total_tokens = getattr(
                    usage, "total_token_count", prompt_tokens + completion_tokens
                )

                span.set_attribute("llm.usage.prompt_tokens", prompt_tokens)
                span.set_attribute("llm.usage.completion_tokens", completion_tokens)
                span.set_attribute("llm.usage.total_tokens", total_tokens)

                # Calculate cost
                cost = self.cost_adapter.calculate_cost(
                    model,
                    {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                    },
                )
                span.set_attribute("llm.cost_usd", cost)

            # Latency
            latency_ms = (time.time() - start_time) * 1000
            span.set_attribute("llm.latency_ms", round(latency_ms, 2))

            # Finish reason (if available)
            if hasattr(result, "candidates") and result.candidates:
                candidate = result.candidates[0]
                if hasattr(candidate, "finish_reason"):
                    span.set_attribute("llm.response.finish_reason", str(candidate.finish_reason))

        except Exception as e:
            # Don't fail the call if metadata extraction fails
            span.set_attribute("llm.metadata_extraction_error", str(e))


# Singleton instance
_google_instrumentation = None


def get_instrumentation() -> GoogleInstrumentation:
    """Get or create the Google instrumentation singleton"""
    global _google_instrumentation
    if _google_instrumentation is None:
        _google_instrumentation = GoogleInstrumentation()
    return _google_instrumentation


def instrument() -> bool:
    """Instrument Google Generative AI SDK"""
    return get_instrumentation().instrument()


def uninstrument() -> bool:
    """Uninstrument Google Generative AI SDK"""
    return get_instrumentation().uninstrument()
