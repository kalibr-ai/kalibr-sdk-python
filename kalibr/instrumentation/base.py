"""
Base instrumentation class for LLM SDKs

Provides common functionality for monkey-patching LLM SDKs and
emitting OpenTelemetry-compatible spans.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode


class BaseInstrumentation(ABC):
    """Base class for LLM SDK instrumentation"""

    def __init__(self, tracer_name: str):
        self.tracer = trace.get_tracer(tracer_name)
        self._is_instrumented = False

    @abstractmethod
    def instrument(self) -> bool:
        """
        Apply monkey-patching to instrument the SDK

        Returns:
            bool: True if instrumentation succeeded, False otherwise
        """
        pass

    @abstractmethod
    def uninstrument(self) -> bool:
        """
        Remove monkey-patching to restore original SDK behavior

        Returns:
            bool: True if uninstrumentation succeeded, False otherwise
        """
        pass

    @property
    def is_instrumented(self) -> bool:
        """Check if SDK is currently instrumented"""
        return self._is_instrumented

    def create_span(self, name: str, attributes: Dict[str, Any], kind: SpanKind = SpanKind.CLIENT):
        """
        Create an OpenTelemetry span with standardized attributes

        Args:
            name: Span name (e.g., "openai.chat.completions.create")
            attributes: Span attributes following OTel semantic conventions
            kind: Span kind (default: CLIENT for LLM API calls)

        Returns:
            Context manager for the span
        """
        return self.tracer.start_as_current_span(name, kind=kind, attributes=attributes)

    @staticmethod
    def set_error(span: trace.Span, error: Exception) -> None:
        """
        Set error status and attributes on a span

        Args:
            span: The span to update
            error: The exception that occurred
        """
        span.set_status(Status(StatusCode.ERROR))
        span.set_attribute("error.type", type(error).__name__)
        span.set_attribute("error.message", str(error))
        span.record_exception(error)


class BaseCostAdapter(ABC):
    """Base class for cost calculation adapters"""

    PRICING: Dict[str, Dict[str, float]] = {}

    @abstractmethod
    def calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """
        Calculate cost in USD for an LLM API call

        Args:
            model: Model identifier (e.g., "gpt-4")
            usage: Token usage dictionary with prompt_tokens, completion_tokens

        Returns:
            Cost in USD (rounded to 6 decimal places)
        """
        pass

    def get_pricing(self, model: str) -> Optional[Dict[str, float]]:
        """
        Get pricing for a specific model

        Args:
            model: Model identifier

        Returns:
            Dictionary with "input" and "output" prices per 1K tokens,
            or None if model not found
        """
        return self.PRICING.get(model)
