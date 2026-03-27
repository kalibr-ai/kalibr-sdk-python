"""LiveKit Agents instrumentor for Kalibr.

Wraps LiveKit Agent pipeline stages (STT -> LLM -> TTS) with
OpenTelemetry spans and cost tracking.
"""

import time
from functools import wraps
from typing import Any, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from kalibr.pricing import compute_voice_cost


class KalibrLiveKitInstrumentor:
    """Instruments LiveKit Agent pipelines with Kalibr tracing.

    Usage:
        from kalibr_voice import KalibrLiveKitInstrumentor

        instrumentor = KalibrLiveKitInstrumentor()
        instrumentor.instrument()

        # LiveKit agent pipeline calls are now traced
    """

    def __init__(self):
        self.tracer = trace.get_tracer("kalibr.livekit")
        self._is_instrumented = False
        self._originals = {}

    def instrument(self) -> bool:
        """Instrument LiveKit Agents pipeline."""
        if self._is_instrumented:
            return True

        try:
            from livekit import agents

            # Instrument STT
            if hasattr(agents, "stt") and hasattr(agents.stt, "STT"):
                stt_cls = agents.stt.STT
                if hasattr(stt_cls, "recognize"):
                    self._originals["stt_recognize"] = stt_cls.recognize
                    stt_cls.recognize = self._wrap_stt(stt_cls.recognize)

            # Instrument TTS
            if hasattr(agents, "tts") and hasattr(agents.tts, "TTS"):
                tts_cls = agents.tts.TTS
                if hasattr(tts_cls, "synthesize"):
                    self._originals["tts_synthesize"] = tts_cls.synthesize
                    tts_cls.synthesize = self._wrap_tts(tts_cls.synthesize)

            self._is_instrumented = True
            return True

        except ImportError:
            print("\u26a0\ufe0f  livekit-agents not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"\u274c Failed to instrument LiveKit Agents: {e}")
            return False

    def uninstrument(self) -> bool:
        """Remove LiveKit Agents instrumentation."""
        if not self._is_instrumented:
            return True

        try:
            from livekit import agents

            if "stt_recognize" in self._originals and hasattr(agents, "stt"):
                agents.stt.STT.recognize = self._originals["stt_recognize"]
            if "tts_synthesize" in self._originals and hasattr(agents, "tts"):
                agents.tts.TTS.synthesize = self._originals["tts_synthesize"]

            self._originals.clear()
            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"\u274c Failed to uninstrument LiveKit Agents: {e}")
            return False

    def _wrap_stt(self, original_func):
        @wraps(original_func)
        async def wrapper(self_instance, *args, **kwargs):
            with self.tracer.start_as_current_span(
                "livekit.stt.recognize",
                kind=SpanKind.CLIENT,
                attributes={
                    "voice.operation": "stt",
                    "llm.vendor": "livekit",
                    "voice.pipeline_stage": "stt",
                },
            ) as span:
                start_time = time.time()
                try:
                    result = await original_func(self_instance, *args, **kwargs)
                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))
                    return result
                except Exception as e:
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise

        return wrapper

    def _wrap_tts(self, original_func):
        @wraps(original_func)
        async def wrapper(self_instance, text: str, *args, **kwargs):
            character_count = len(text) if isinstance(text, str) else 0
            with self.tracer.start_as_current_span(
                "livekit.tts.synthesize",
                kind=SpanKind.CLIENT,
                attributes={
                    "voice.operation": "tts",
                    "llm.vendor": "livekit",
                    "voice.pipeline_stage": "tts",
                    "voice.character_count": character_count,
                },
            ) as span:
                start_time = time.time()
                try:
                    result = await original_func(self_instance, text, *args, **kwargs)
                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", round(latency_ms, 2))
                    return result
                except Exception as e:
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise

        return wrapper
