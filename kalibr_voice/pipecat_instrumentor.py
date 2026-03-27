"""Pipecat instrumentor for Kalibr.

Wraps Pipecat pipeline processors with OpenTelemetry spans
and cost tracking.
"""

import time
from functools import wraps
from typing import Any, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from kalibr.pricing import compute_voice_cost


class KalibrPipecatInstrumentor:
    """Instruments Pipecat pipelines with Kalibr tracing.

    Usage:
        from kalibr_voice import KalibrPipecatInstrumentor

        instrumentor = KalibrPipecatInstrumentor()
        instrumentor.instrument()

        # Pipecat pipeline processor calls are now traced
    """

    def __init__(self):
        self.tracer = trace.get_tracer("kalibr.pipecat")
        self._is_instrumented = False
        self._originals = {}

    def instrument(self) -> bool:
        """Instrument Pipecat pipeline processors."""
        if self._is_instrumented:
            return True

        try:
            from pipecat.services import tts as pipecat_tts
            from pipecat.services import stt as pipecat_stt

            # Instrument TTS service base
            if hasattr(pipecat_tts, "TTSService"):
                tts_cls = pipecat_tts.TTSService
                if hasattr(tts_cls, "run_tts"):
                    self._originals["tts_run_tts"] = tts_cls.run_tts
                    tts_cls.run_tts = self._wrap_tts(tts_cls.run_tts)

            # Instrument STT service base
            if hasattr(pipecat_stt, "STTService"):
                stt_cls = pipecat_stt.STTService
                if hasattr(stt_cls, "run_stt"):
                    self._originals["stt_run_stt"] = stt_cls.run_stt
                    stt_cls.run_stt = self._wrap_stt(stt_cls.run_stt)

            self._is_instrumented = True
            return True

        except ImportError:
            print("\u26a0\ufe0f  pipecat-ai not installed, skipping instrumentation")
            return False
        except Exception as e:
            print(f"\u274c Failed to instrument Pipecat: {e}")
            return False

    def uninstrument(self) -> bool:
        """Remove Pipecat instrumentation."""
        if not self._is_instrumented:
            return True

        try:
            from pipecat.services import tts as pipecat_tts
            from pipecat.services import stt as pipecat_stt

            if "tts_run_tts" in self._originals and hasattr(pipecat_tts, "TTSService"):
                pipecat_tts.TTSService.run_tts = self._originals["tts_run_tts"]
            if "stt_run_stt" in self._originals and hasattr(pipecat_stt, "STTService"):
                pipecat_stt.STTService.run_stt = self._originals["stt_run_stt"]

            self._originals.clear()
            self._is_instrumented = False
            return True

        except Exception as e:
            print(f"\u274c Failed to uninstrument Pipecat: {e}")
            return False

    def _wrap_tts(self, original_func):
        @wraps(original_func)
        async def wrapper(self_instance, text: str, *args, **kwargs):
            character_count = len(text) if isinstance(text, str) else 0
            with self.tracer.start_as_current_span(
                "pipecat.tts.run_tts",
                kind=SpanKind.CLIENT,
                attributes={
                    "voice.operation": "tts",
                    "llm.vendor": "pipecat",
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

    def _wrap_stt(self, original_func):
        @wraps(original_func)
        async def wrapper(self_instance, *args, **kwargs):
            with self.tracer.start_as_current_span(
                "pipecat.stt.run_stt",
                kind=SpanKind.CLIENT,
                attributes={
                    "voice.operation": "stt",
                    "llm.vendor": "pipecat",
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
