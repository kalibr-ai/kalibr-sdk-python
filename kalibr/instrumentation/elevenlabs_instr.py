"""
ElevenLabs SDK Instrumentation

Monkey-patches the ElevenLabs SDK to automatically emit OpenTelemetry spans
for text-to-speech API calls.

Thread-safe singleton pattern using double-checked locking.
"""

import threading
import time
from functools import wraps
from typing import Any, Dict, Optional

from opentelemetry.trace import SpanKind

from kalibr.pricing import compute_cost_flexible

from .base import FlexibleCostAdapter, BaseInstrumentation


class ElevenLabsCostAdapter(FlexibleCostAdapter):
    """Cost calculation adapter for ElevenLabs voice models."""

    def get_vendor_name(self) -> str:
        return "elevenlabs"

    def calculate_cost(self, model: str, usage_metrics: Dict[str, Any]) -> float:
        return compute_cost_flexible("elevenlabs", model, usage_metrics)

    def get_usage_metrics(self, response: Any) -> Dict[str, Any]:
        return {}


class ElevenLabsInstrumentation(BaseInstrumentation):
    """Instrumentation for ElevenLabs SDK"""

    def __init__(self):
        super().__init__("kalibr.elevenlabs")
        self._original_generate = None
        self._original_async_generate = None
        self._original_convert = None
        self._original_async_convert = None
        self.cost_adapter = ElevenLabsCostAdapter()

    def instrument(self) -> bool:
        if self._is_instrumented:
            return True

        try:
            import elevenlabs
            from elevenlabs.client import ElevenLabs

            # Patch sync generate
            if hasattr(ElevenLabs, "generate"):
                self._original_generate = ElevenLabs.generate
                ElevenLabs.generate = self._traced_generate_wrapper(ElevenLabs.generate)

            # Patch async generate
            try:
                from elevenlabs.client import AsyncElevenLabs

                if hasattr(AsyncElevenLabs, "generate"):
                    self._original_async_generate = AsyncElevenLabs.generate
                    AsyncElevenLabs.generate = self._traced_async_generate_wrapper(
                        AsyncElevenLabs.generate
                    )
            except (ImportError, AttributeError):
                pass

            # Patch text_to_speech.convert (lower-level API)
            try:
                from elevenlabs.client import ElevenLabs as EL

                if hasattr(EL, "text_to_speech") and hasattr(
                    getattr(EL, "text_to_speech", None).__class__, "convert"
                    if hasattr(EL, "text_to_speech")
                    else None,
                    "__call__",
                ):
                    pass  # Will be patched on instance level if needed
            except (ImportError, AttributeError):
                pass

            self._is_instrumented = True
            return True

        except ImportError:
            print("\u26a0\ufe0f  ElevenLabs SDK not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"\u274c Failed to instrument ElevenLabs SDK: {e}")
            return False

    def uninstrument(self) -> bool:
        if not self._is_instrumented:
            return True

        try:
            from elevenlabs.client import ElevenLabs

            if self._original_generate:
                ElevenLabs.generate = self._original_generate

            try:
                from elevenlabs.client import AsyncElevenLabs

                if self._original_async_generate:
                    AsyncElevenLabs.generate = self._original_async_generate
            except (ImportError, AttributeError):
                pass

            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"\u274c Failed to uninstrument ElevenLabs SDK: {e}")
            return False

    def _traced_generate_wrapper(self, original_func):
        @wraps(original_func)
        def wrapper(self_instance, *args, **kwargs):
            text = kwargs.get("text", args[0] if args else "")
            voice = kwargs.get("voice", "")
            model = kwargs.get("model", "eleven_multilingual_v2")
            character_count = len(text) if isinstance(text, str) else 0

            voice_id = voice if isinstance(voice, str) else getattr(voice, "voice_id", str(voice))

            with self.tracer.start_as_current_span(
                "elevenlabs.generate",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "elevenlabs",
                    "llm.system": "elevenlabs",
                    "voice.operation": "tts",
                    "voice.character_count": character_count,
                    "voice.voice_id": str(voice_id),
                    "voice.model_id": str(model),
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

                    cost = self.cost_adapter.calculate_cost(
                        str(model), {"characters": character_count}
                    )
                    span.set_attribute("llm.cost_usd", cost)

                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))

                    return result

                except Exception as e:
                    self.set_error(span, e)
                    raise

        return wrapper

    def _traced_async_generate_wrapper(self, original_func):
        @wraps(original_func)
        async def wrapper(self_instance, *args, **kwargs):
            text = kwargs.get("text", args[0] if args else "")
            voice = kwargs.get("voice", "")
            model = kwargs.get("model", "eleven_multilingual_v2")
            character_count = len(text) if isinstance(text, str) else 0

            voice_id = voice if isinstance(voice, str) else getattr(voice, "voice_id", str(voice))

            with self.tracer.start_as_current_span(
                "elevenlabs.generate",
                kind=SpanKind.CLIENT,
                attributes={
                    "llm.vendor": "elevenlabs",
                    "llm.system": "elevenlabs",
                    "voice.operation": "tts",
                    "voice.character_count": character_count,
                    "voice.voice_id": str(voice_id),
                    "voice.model_id": str(model),
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

                    cost = self.cost_adapter.calculate_cost(
                        str(model), {"characters": character_count}
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
_elevenlabs_instrumentation = None
_elevenlabs_lock = threading.Lock()


def get_instrumentation() -> ElevenLabsInstrumentation:
    global _elevenlabs_instrumentation
    if _elevenlabs_instrumentation is None:
        with _elevenlabs_lock:
            if _elevenlabs_instrumentation is None:
                _elevenlabs_instrumentation = ElevenLabsInstrumentation()
    return _elevenlabs_instrumentation


def instrument() -> bool:
    return get_instrumentation().instrument()


def uninstrument() -> bool:
    return get_instrumentation().uninstrument()
