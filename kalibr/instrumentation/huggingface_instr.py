"""
HuggingFace InferenceClient Instrumentation

Monkey-patches the huggingface_hub InferenceClient and AsyncInferenceClient
to automatically emit OpenTelemetry spans for all task-specific API calls.

Covers text, audio, image, embedding, and classification tasks via a single
instrumentor, since all go through the same InferenceClient SDK.

Thread-safe singleton pattern using double-checked locking.
"""

import threading
import time
from functools import wraps
from typing import Any, Dict, Optional

from opentelemetry.trace import SpanKind

from .base import BaseCostAdapter, BaseInstrumentation


# Task type to modality mapping
TASK_MODALITY = {
    "chat_completion": "text",
    "text_generation": "text",
    "translation": "text",
    "summarization": "text",
    "automatic_speech_recognition": "audio",
    "text_to_speech": "audio",
    "text_to_image": "image",
    "feature_extraction": "embedding",
    "text_classification": "classification",
}

# Methods to patch on InferenceClient / AsyncInferenceClient
PATCHED_METHODS = [
    "chat_completion",
    "text_generation",
    "automatic_speech_recognition",
    "text_to_speech",
    "text_to_image",
    "feature_extraction",
    "text_classification",
    "translation",
    "summarization",
]


def _extract_metrics(task: str, response: Any) -> dict:
    """Extract task-appropriate usage metrics from a HuggingFace response.

    Args:
        task: The task name (e.g. "chat_completion", "text_to_image")
        response: The raw response object from the InferenceClient

    Returns:
        Dictionary of usage metrics appropriate for the task type.
    """
    metrics: dict = {}

    if task in ("chat_completion",):
        # ChatCompletionOutput has .usage with .prompt_tokens / .completion_tokens
        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            metrics["input_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
            metrics["output_tokens"] = getattr(usage, "completion_tokens", 0) or 0
        elif isinstance(response, dict):
            usage = response.get("usage", {})
            metrics["input_tokens"] = usage.get("prompt_tokens", 0)
            metrics["output_tokens"] = usage.get("completion_tokens", 0)

    elif task in ("text_generation", "translation", "summarization"):
        # TextGenerationOutput may carry token counts in .details
        if hasattr(response, "details") and response.details:
            details = response.details
            metrics["input_tokens"] = getattr(details, "prefill_tokens", 0) or 0
            metrics["output_tokens"] = getattr(details, "generated_tokens", 0) or 0
        elif isinstance(response, dict):
            details = response.get("details", {}) or {}
            metrics["input_tokens"] = details.get("prefill_tokens", 0)
            metrics["output_tokens"] = details.get("generated_tokens", 0)

    elif task == "automatic_speech_recognition":
        # ASR output may include duration metadata
        if isinstance(response, dict):
            metrics["audio_duration_ms"] = response.get("audio_duration_ms", 0)
        elif hasattr(response, "audio_duration_ms"):
            metrics["audio_duration_ms"] = response.audio_duration_ms or 0
        # Fallback: check for chunks with timestamps
        if not metrics.get("audio_duration_ms"):
            chunks = None
            if hasattr(response, "chunks"):
                chunks = response.chunks
            elif isinstance(response, dict):
                chunks = response.get("chunks")
            if chunks and len(chunks) > 0:
                last = chunks[-1]
                ts = getattr(last, "timestamp", None) or (
                    last.get("timestamp") if isinstance(last, dict) else None
                )
                if ts and len(ts) >= 2:
                    metrics["audio_duration_ms"] = int(ts[1] * 1000)

    elif task == "text_to_speech":
        if isinstance(response, bytes):
            metrics["audio_bytes"] = len(response)
        if hasattr(response, "audio_duration_ms"):
            metrics["audio_duration_ms"] = response.audio_duration_ms or 0

    elif task == "text_to_image":
        metrics["image_count"] = 1
        if hasattr(response, "size"):
            w, h = response.size
            metrics["image_resolution"] = f"{w}x{h}"
        elif hasattr(response, "width") and hasattr(response, "height"):
            metrics["image_resolution"] = f"{response.width}x{response.height}"

    elif task == "feature_extraction":
        # Embedding result is typically a list of floats or nested list
        if isinstance(response, list):
            if len(response) > 0 and isinstance(response[0], list):
                metrics["vector_dimensions"] = len(response[0])
            elif len(response) > 0 and isinstance(response[0], (int, float)):
                metrics["vector_dimensions"] = len(response)

    elif task == "text_classification":
        if isinstance(response, list) and len(response) > 0:
            metrics["label_count"] = len(response)

    return metrics


class HuggingFaceCostAdapter(BaseCostAdapter):
    """Cost calculation adapter for HuggingFace models.

    Extends BaseCostAdapter with flexible cost computation that handles
    multiple modalities (text tokens, audio duration, image generation).
    Uses centralized pricing from kalibr.pricing module.
    """

    def get_vendor_name(self) -> str:
        return "huggingface"

    def calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Calculate cost in USD for a HuggingFace API call.

        For token-based tasks, uses centralized per-token pricing.
        For other modalities, returns 0.0 (HuggingFace Inference API
        pricing varies by deployment; token-based is the common case).

        Args:
            model: Model identifier (e.g. "meta-llama/Llama-3-8B-Instruct")
            usage: Usage dict with input_tokens/output_tokens or other metrics

        Returns:
            Cost in USD (rounded to 6 decimal places)
        """
        return self.compute_cost_flexible(model, usage)

    def compute_cost_flexible(self, model: str, usage: Dict[str, Any]) -> float:
        """Compute cost for any modality using flexible usage metrics.

        Args:
            model: Model identifier
            usage: Dict that may contain token counts, audio duration, etc.

        Returns:
            Cost in USD (rounded to 6 decimal places)
        """
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        if input_tokens or output_tokens:
            pricing = self.get_pricing_for_model(model)
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            return round(input_cost + output_cost, 6)

        # Non-token modalities: HuggingFace Inference API pricing is
        # deployment-dependent. Return 0 rather than guess.
        return 0.0

    def get_usage_metrics(self, task: str, response: Any) -> dict:
        """Extract usage metrics from a response based on task type.

        Convenience method wrapping the module-level _extract_metrics.

        Args:
            task: Task name (e.g. "chat_completion")
            response: Raw response from InferenceClient

        Returns:
            Dict of usage metrics
        """
        return _extract_metrics(task, response)


class HuggingFaceInstrumentation(BaseInstrumentation):
    """Instrumentation for HuggingFace InferenceClient SDK"""

    def __init__(self):
        super().__init__("kalibr.huggingface")
        self._originals: Dict[str, Any] = {}
        self._async_originals: Dict[str, Any] = {}
        self.cost_adapter = HuggingFaceCostAdapter()

    def instrument(self) -> bool:
        """Apply monkey-patching to HuggingFace InferenceClient"""
        if self._is_instrumented:
            return True

        try:
            from huggingface_hub import InferenceClient

            # Patch sync methods
            for method_name in PATCHED_METHODS:
                if hasattr(InferenceClient, method_name):
                    original = getattr(InferenceClient, method_name)
                    self._originals[method_name] = original
                    setattr(
                        InferenceClient,
                        method_name,
                        self._traced_wrapper(original, method_name),
                    )

            # Patch async methods
            try:
                from huggingface_hub import AsyncInferenceClient

                for method_name in PATCHED_METHODS:
                    if hasattr(AsyncInferenceClient, method_name):
                        original = getattr(AsyncInferenceClient, method_name)
                        self._async_originals[method_name] = original
                        setattr(
                            AsyncInferenceClient,
                            method_name,
                            self._traced_async_wrapper(original, method_name),
                        )
            except ImportError:
                pass  # AsyncInferenceClient may not be available

            self._is_instrumented = True
            return True

        except ImportError:
            print("⚠️  huggingface_hub not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"❌ Failed to instrument HuggingFace SDK: {e}")
            return False

    def uninstrument(self) -> bool:
        """Remove monkey-patching from HuggingFace InferenceClient"""
        if not self._is_instrumented:
            return True

        try:
            from huggingface_hub import InferenceClient

            for method_name, original in self._originals.items():
                setattr(InferenceClient, method_name, original)
            self._originals.clear()

            try:
                from huggingface_hub import AsyncInferenceClient

                for method_name, original in self._async_originals.items():
                    setattr(AsyncInferenceClient, method_name, original)
                self._async_originals.clear()
            except ImportError:
                pass

            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"❌ Failed to uninstrument HuggingFace SDK: {e}")
            return False

    def _traced_wrapper(self, original_func, task_name: str):
        """Create a sync wrapper that traces a task method."""

        @wraps(original_func)
        def wrapper(client_self, *args, **kwargs):
            model = kwargs.get("model", getattr(client_self, "model", None) or "unknown")
            modality = TASK_MODALITY.get(task_name, "unknown")

            with self.tracer.start_as_current_span(
                f"huggingface.{task_name}",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "huggingface",
                    "llm.request.model": str(model),
                    "llm.system": "huggingface",
                    "kalibr.modality": modality,
                    "kalibr.task_type": task_name,
                },
            ) as span:
                start_time = time.time()

                try:
                    from kalibr.context import inject_kalibr_context_into_span

                    inject_kalibr_context_into_span(span)
                except Exception:
                    pass

                try:
                    result = original_func(client_self, *args, **kwargs)
                    self._set_response_attributes(span, task_name, model, result, start_time)
                    return result
                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _traced_async_wrapper(self, original_func, task_name: str):
        """Create an async wrapper that traces a task method."""

        @wraps(original_func)
        async def wrapper(client_self, *args, **kwargs):
            model = kwargs.get("model", getattr(client_self, "model", None) or "unknown")
            modality = TASK_MODALITY.get(task_name, "unknown")

            with self.tracer.start_as_current_span(
                f"huggingface.{task_name}",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "huggingface",
                    "llm.request.model": str(model),
                    "llm.system": "huggingface",
                    "kalibr.modality": modality,
                    "kalibr.task_type": task_name,
                },
            ) as span:
                start_time = time.time()

                try:
                    from kalibr.context import inject_kalibr_context_into_span

                    inject_kalibr_context_into_span(span)
                except Exception:
                    pass

                try:
                    result = await original_func(client_self, *args, **kwargs)
                    self._set_response_attributes(span, task_name, model, result, start_time)
                    return result
                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _set_response_attributes(
        self, span, task_name: str, model: Any, result: Any, start_time: float
    ) -> None:
        """Extract metadata from response and set span attributes."""
        try:
            # Response model (some responses carry the model used)
            if hasattr(result, "model"):
                span.set_attribute("llm.response.model", str(result.model))

            # Latency
            latency_ms = (time.time() - start_time) * 1000
            span.set_attribute("llm.latency_ms", round(latency_ms, 2))

            # Task-specific usage metrics
            metrics = self.cost_adapter.get_usage_metrics(task_name, result)

            # Set metric attributes on span
            for key, value in metrics.items():
                span.set_attribute(f"llm.usage.{key}", value)

            # Calculate cost
            cost = self.cost_adapter.compute_cost_flexible(str(model), metrics)
            span.set_attribute("llm.cost_usd", cost)

            # Response ID
            if hasattr(result, "id"):
                span.set_attribute("llm.response.id", result.id)

        except Exception as e:
            span.set_attribute("llm.metadata_extraction_error", str(e))


# Singleton instance
_huggingface_instrumentation = None
_huggingface_lock = threading.Lock()


def get_instrumentation() -> HuggingFaceInstrumentation:
    """Get or create the HuggingFace instrumentation singleton.

    Thread-safe singleton pattern using double-checked locking.
    """
    global _huggingface_instrumentation
    if _huggingface_instrumentation is None:
        with _huggingface_lock:
            if _huggingface_instrumentation is None:
                _huggingface_instrumentation = HuggingFaceInstrumentation()
    return _huggingface_instrumentation


def instrument() -> bool:
    """Instrument HuggingFace SDK"""
    return get_instrumentation().instrument()


def uninstrument() -> bool:
    """Uninstrument HuggingFace SDK"""
    return get_instrumentation().uninstrument()
