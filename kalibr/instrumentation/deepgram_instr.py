"""
Deepgram SDK Instrumentation

Monkey-patches the Deepgram SDK to automatically emit OpenTelemetry spans
for speech-to-text API calls (REST methods only; WebSocket deferred).

Thread-safe singleton pattern using double-checked locking.
"""

import threading
import time
from functools import wraps
from typing import Any, Dict, Optional

from opentelemetry.trace import SpanKind

from .base import BaseVoiceCostAdapter, BaseInstrumentation


class DeepgramCostAdapter(BaseVoiceCostAdapter):
    """Cost calculation adapter for Deepgram voice models."""

    def get_vendor_name(self) -> str:
        return "deepgram"

    def calculate_cost(self, model: str, usage: Dict[str, Any]) -> float:
        pricing = self.get_voice_pricing_for_model(model)
        if pricing["unit"] == "per_minute":
            duration_min = usage.get("audio_duration_minutes", 0.0)
            cost = duration_min * pricing["price"]
        elif pricing["unit"] == "per_1k_chars":
            characters = usage.get("characters", 0)
            cost = (characters / 1_000) * pricing["price"]
        else:
            cost = 0.0
        return round(cost, 6)


class DeepgramInstrumentation(BaseInstrumentation):
    """Instrumentation for Deepgram SDK"""

    def __init__(self):
        super().__init__("kalibr.deepgram")
        self._original_transcribe_file = None
        self._original_transcribe_url = None
        self._original_async_transcribe_file = None
        self._original_async_transcribe_url = None
        self.cost_adapter = DeepgramCostAdapter()

    def instrument(self) -> bool:
        if self._is_instrumented:
            return True

        try:
            from deepgram import DeepgramClient

            # Patch sync listen REST methods
            try:
                from deepgram.clients.listen.v1.rest import ListenRESTClient

                if hasattr(ListenRESTClient, "transcribe_file"):
                    self._original_transcribe_file = ListenRESTClient.transcribe_file
                    ListenRESTClient.transcribe_file = self._traced_transcribe_wrapper(
                        ListenRESTClient.transcribe_file, "file"
                    )

                if hasattr(ListenRESTClient, "transcribe_url"):
                    self._original_transcribe_url = ListenRESTClient.transcribe_url
                    ListenRESTClient.transcribe_url = self._traced_transcribe_wrapper(
                        ListenRESTClient.transcribe_url, "url"
                    )
            except ImportError:
                # Try alternate module path for different SDK versions
                try:
                    from deepgram.clients.listen.v1 import rest as listen_rest

                    if hasattr(listen_rest, "ListenRESTClient"):
                        cls = listen_rest.ListenRESTClient
                        if hasattr(cls, "transcribe_file"):
                            self._original_transcribe_file = cls.transcribe_file
                            cls.transcribe_file = self._traced_transcribe_wrapper(
                                cls.transcribe_file, "file"
                            )
                        if hasattr(cls, "transcribe_url"):
                            self._original_transcribe_url = cls.transcribe_url
                            cls.transcribe_url = self._traced_transcribe_wrapper(
                                cls.transcribe_url, "url"
                            )
                except ImportError:
                    pass

            # Patch async methods
            try:
                from deepgram.clients.listen.v1.rest import AsyncListenRESTClient

                if hasattr(AsyncListenRESTClient, "transcribe_file"):
                    self._original_async_transcribe_file = AsyncListenRESTClient.transcribe_file
                    AsyncListenRESTClient.transcribe_file = (
                        self._traced_async_transcribe_wrapper(
                            AsyncListenRESTClient.transcribe_file, "file"
                        )
                    )

                if hasattr(AsyncListenRESTClient, "transcribe_url"):
                    self._original_async_transcribe_url = AsyncListenRESTClient.transcribe_url
                    AsyncListenRESTClient.transcribe_url = (
                        self._traced_async_transcribe_wrapper(
                            AsyncListenRESTClient.transcribe_url, "url"
                        )
                    )
            except ImportError:
                pass

            self._is_instrumented = True
            return True

        except ImportError:
            print("\u26a0\ufe0f  Deepgram SDK not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"\u274c Failed to instrument Deepgram SDK: {e}")
            return False

    def uninstrument(self) -> bool:
        if not self._is_instrumented:
            return True

        try:
            try:
                from deepgram.clients.listen.v1.rest import ListenRESTClient

                if self._original_transcribe_file:
                    ListenRESTClient.transcribe_file = self._original_transcribe_file
                if self._original_transcribe_url:
                    ListenRESTClient.transcribe_url = self._original_transcribe_url
            except ImportError:
                pass

            try:
                from deepgram.clients.listen.v1.rest import AsyncListenRESTClient

                if self._original_async_transcribe_file:
                    AsyncListenRESTClient.transcribe_file = self._original_async_transcribe_file
                if self._original_async_transcribe_url:
                    AsyncListenRESTClient.transcribe_url = self._original_async_transcribe_url
            except ImportError:
                pass

            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"\u274c Failed to uninstrument Deepgram SDK: {e}")
            return False

    def _extract_duration_ms(self, result: Any) -> float:
        """Extract audio duration in milliseconds from Deepgram response."""
        try:
            if hasattr(result, "metadata") and hasattr(result.metadata, "duration"):
                return result.metadata.duration * 1000
            if hasattr(result, "results") and hasattr(result.results, "channels"):
                for channel in result.results.channels:
                    for alt in getattr(channel, "alternatives", []):
                        if hasattr(alt, "words") and alt.words:
                            last_word = alt.words[-1]
                            return (getattr(last_word, "end", 0)) * 1000
        except Exception:
            pass
        return 0.0

    def _extract_model(self, kwargs: dict) -> str:
        """Extract model from Deepgram options."""
        options = kwargs.get("options", None)
        if options is not None:
            if hasattr(options, "model"):
                return options.model or "nova-2"
            if isinstance(options, dict):
                return options.get("model", "nova-2")
        return "nova-2"

    def _traced_transcribe_wrapper(self, original_func, source_type: str):
        @wraps(original_func)
        def wrapper(self_instance, *args, **kwargs):
            model = self._extract_model(kwargs)

            with self.tracer.start_as_current_span(
                "deepgram.transcribe",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "deepgram",
                    "llm.system": "deepgram",
                    "voice.operation": "stt",
                    "voice.model_id": model,
                    "voice.source_type": source_type,
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

                    duration_ms = self._extract_duration_ms(result)
                    span.set_attribute("voice.audio_duration_ms", duration_ms)

                    duration_min = duration_ms / 60_000
                    cost = self.cost_adapter.calculate_cost(
                        model, {"audio_duration_minutes": duration_min}
                    )
                    span.set_attribute("llm.cost_usd", cost)

                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _traced_async_transcribe_wrapper(self, original_func, source_type: str):
        @wraps(original_func)
        async def wrapper(self_instance, *args, **kwargs):
            model = self._extract_model(kwargs)

            with self.tracer.start_as_current_span(
                "deepgram.transcribe",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "deepgram",
                    "llm.system": "deepgram",
                    "voice.operation": "stt",
                    "voice.model_id": model,
                    "voice.source_type": source_type,
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

                    duration_ms = self._extract_duration_ms(result)
                    span.set_attribute("voice.audio_duration_ms", duration_ms)

                    duration_min = duration_ms / 60_000
                    cost = self.cost_adapter.calculate_cost(
                        model, {"audio_duration_minutes": duration_min}
                    )
                    span.set_attribute("llm.cost_usd", cost)

                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper


# Singleton instance
_deepgram_instrumentation = None
_deepgram_lock = threading.Lock()


def get_instrumentation() -> DeepgramInstrumentation:
    global _deepgram_instrumentation
    if _deepgram_instrumentation is None:
        with _deepgram_lock:
            if _deepgram_instrumentation is None:
                _deepgram_instrumentation = DeepgramInstrumentation()
    return _deepgram_instrumentation


def instrument() -> bool:
    return get_instrumentation().instrument()


def uninstrument() -> bool:
    return get_instrumentation().uninstrument()
