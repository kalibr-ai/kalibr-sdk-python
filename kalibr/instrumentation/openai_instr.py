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

from kalibr.pricing import compute_cost_flexible

from .base import BaseCostAdapter, BaseInstrumentation, FlexibleCostAdapter


class OpenAICostAdapter(BaseCostAdapter):
    """Cost calculation adapter for OpenAI models.

    Uses centralized pricing from kalibr.pricing module.
    """

    def get_vendor_name(self) -> str:
        return "openai"

    def calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        pricing = self.get_pricing_for_model(model)

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)


class OpenAIVoiceCostAdapter(FlexibleCostAdapter):
    """Cost calculation adapter for OpenAI voice models (TTS/STT)."""

    def get_vendor_name(self) -> str:
        return "openai"

    def calculate_cost(self, model: str, usage_metrics: Dict[str, Any]) -> float:
        return compute_cost_flexible("openai", model, usage_metrics)

    def get_usage_metrics(self, response: Any) -> Dict[str, Any]:
        return {}


class OpenAIInstrumentation(BaseInstrumentation):
    """Instrumentation for OpenAI SDK"""

    def __init__(self):
        super().__init__("kalibr.openai")
        self._original_create = None
        self._original_async_create = None
        self._original_speech_create = None
        self._original_async_speech_create = None
        self._original_transcription_create = None
        self._original_async_transcription_create = None
        self.cost_adapter = OpenAICostAdapter()
        self.voice_cost_adapter = OpenAIVoiceCostAdapter()

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

            # Patch audio speech (TTS)
            try:
                from openai.resources.audio import speech

                if hasattr(speech.Speech, "create"):
                    self._original_speech_create = speech.Speech.create
                    speech.Speech.create = self._traced_speech_create_wrapper(
                        speech.Speech.create
                    )
                if hasattr(speech, "AsyncSpeech") and hasattr(speech.AsyncSpeech, "create"):
                    self._original_async_speech_create = speech.AsyncSpeech.create
                    speech.AsyncSpeech.create = self._traced_async_speech_create_wrapper(
                        speech.AsyncSpeech.create
                    )
            except (ImportError, AttributeError):
                pass

            # Patch audio transcriptions (STT)
            try:
                from openai.resources.audio import transcriptions

                if hasattr(transcriptions.Transcriptions, "create"):
                    self._original_transcription_create = transcriptions.Transcriptions.create
                    transcriptions.Transcriptions.create = (
                        self._traced_transcription_create_wrapper(
                            transcriptions.Transcriptions.create
                        )
                    )
                if hasattr(transcriptions, "AsyncTranscriptions") and hasattr(
                    transcriptions.AsyncTranscriptions, "create"
                ):
                    self._original_async_transcription_create = (
                        transcriptions.AsyncTranscriptions.create
                    )
                    transcriptions.AsyncTranscriptions.create = (
                        self._traced_async_transcription_create_wrapper(
                            transcriptions.AsyncTranscriptions.create
                        )
                    )
            except (ImportError, AttributeError):
                pass

            self._is_instrumented = True
            return True

        except ImportError:
            print("\u26a0\ufe0f  OpenAI SDK not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"\u274c Failed to instrument OpenAI SDK: {e}")
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

            # Restore audio speech
            try:
                from openai.resources.audio import speech

                if self._original_speech_create:
                    speech.Speech.create = self._original_speech_create
                if self._original_async_speech_create:
                    speech.AsyncSpeech.create = self._original_async_speech_create
            except (ImportError, AttributeError):
                pass

            # Restore audio transcriptions
            try:
                from openai.resources.audio import transcriptions

                if self._original_transcription_create:
                    transcriptions.Transcriptions.create = self._original_transcription_create
                if self._original_async_transcription_create:
                    transcriptions.AsyncTranscriptions.create = (
                        self._original_async_transcription_create
                    )
            except (ImportError, AttributeError):
                pass

            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"\u274c Failed to uninstrument OpenAI SDK: {e}")
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

    def _traced_speech_create_wrapper(self, original_func):
        @wraps(original_func)
        def wrapper(self_instance, *args, **kwargs):
            model = kwargs.get("model", "tts-1")
            input_text = kwargs.get("input", "")
            character_count = len(input_text) if isinstance(input_text, str) else 0

            with self.tracer.start_as_current_span(
                "openai.audio.speech.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "openai",
                    "llm.system": "openai",
                    "llm.request.model": model,
                    "voice.operation": "tts",
                    "voice.character_count": character_count,
                    "voice.model_id": model,
                    "voice.voice_id": kwargs.get("voice", ""),
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

                    cost = self.voice_cost_adapter.calculate_cost(
                        model, {"characters": character_count}
                    )
                    span.set_attribute("llm.cost_usd", cost)

                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _traced_async_speech_create_wrapper(self, original_func):
        @wraps(original_func)
        async def wrapper(self_instance, *args, **kwargs):
            model = kwargs.get("model", "tts-1")
            input_text = kwargs.get("input", "")
            character_count = len(input_text) if isinstance(input_text, str) else 0

            with self.tracer.start_as_current_span(
                "openai.audio.speech.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "openai",
                    "llm.system": "openai",
                    "llm.request.model": model,
                    "voice.operation": "tts",
                    "voice.character_count": character_count,
                    "voice.model_id": model,
                    "voice.voice_id": kwargs.get("voice", ""),
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

                    cost = self.voice_cost_adapter.calculate_cost(
                        model, {"characters": character_count}
                    )
                    span.set_attribute("llm.cost_usd", cost)

                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _traced_transcription_create_wrapper(self, original_func):
        @wraps(original_func)
        def wrapper(self_instance, *args, **kwargs):
            model = kwargs.get("model", "whisper-1")

            with self.tracer.start_as_current_span(
                "openai.audio.transcriptions.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "openai",
                    "llm.system": "openai",
                    "llm.request.model": model,
                    "voice.operation": "stt",
                    "voice.model_id": model,
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

                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _traced_async_transcription_create_wrapper(self, original_func):
        @wraps(original_func)
        async def wrapper(self_instance, *args, **kwargs):
            model = kwargs.get("model", "whisper-1")

            with self.tracer.start_as_current_span(
                "openai.audio.transcriptions.create",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "openai",
                    "llm.system": "openai",
                    "llm.request.model": model,
                    "voice.operation": "stt",
                    "voice.model_id": model,
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

                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))

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
