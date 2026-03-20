"""Tests for voice SDK instrumentation.

Tests ElevenLabs, Deepgram, and OpenAI audio instrumentation
using mocked SDKs. All adapters now use FlexibleCostAdapter
and compute_cost_flexible().
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from kalibr.pricing import compute_cost_flexible


class TestElevenLabsCostAdapter:
    """Tests for ElevenLabs instrumentation cost adapter"""

    def test_cost_calculation(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter

        adapter = ElevenLabsCostAdapter()
        cost = adapter.calculate_cost(
            "eleven_multilingual_v2", {"characters": 3000}
        )
        expected = compute_cost_flexible(
            "elevenlabs", "eleven_multilingual_v2", {"characters": 3000}
        )
        assert cost == expected

    def test_cost_calculation_turbo(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter

        adapter = ElevenLabsCostAdapter()
        cost = adapter.calculate_cost(
            "eleven_turbo_v2", {"characters": 1000}
        )
        expected = compute_cost_flexible(
            "elevenlabs", "eleven_turbo_v2", {"characters": 1000}
        )
        assert cost == expected

    def test_zero_characters(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter

        adapter = ElevenLabsCostAdapter()
        cost = adapter.calculate_cost("eleven_multilingual_v2", {"characters": 0})
        assert cost == 0.0

    def test_vendor_name(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter

        adapter = ElevenLabsCostAdapter()
        assert adapter.get_vendor_name() == "elevenlabs"

    def test_is_flexible_adapter(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter
        from kalibr.instrumentation.base import FlexibleCostAdapter

        adapter = ElevenLabsCostAdapter()
        assert isinstance(adapter, FlexibleCostAdapter)


class TestDeepgramCostAdapter:
    """Tests for Deepgram instrumentation cost adapter"""

    def test_cost_calculation_stt(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter

        adapter = DeepgramCostAdapter()
        cost = adapter.calculate_cost(
            "nova-2", {"audio_seconds": 600.0}
        )
        expected = compute_cost_flexible(
            "deepgram", "nova-2", {"audio_seconds": 600.0}
        )
        assert cost == expected

    def test_cost_calculation_tts(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter

        adapter = DeepgramCostAdapter()
        cost = adapter.calculate_cost(
            "aura-asteria-en", {"characters": 1000}
        )
        expected = compute_cost_flexible(
            "deepgram", "aura-asteria-en", {"characters": 1000}
        )
        assert cost == expected

    def test_zero_duration(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter

        adapter = DeepgramCostAdapter()
        cost = adapter.calculate_cost("nova-2", {"audio_seconds": 0.0})
        assert cost == 0.0

    def test_vendor_name(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter

        adapter = DeepgramCostAdapter()
        assert adapter.get_vendor_name() == "deepgram"

    def test_is_flexible_adapter(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter
        from kalibr.instrumentation.base import FlexibleCostAdapter

        adapter = DeepgramCostAdapter()
        assert isinstance(adapter, FlexibleCostAdapter)


class TestOpenAIVoiceCostAdapter:
    """Tests for OpenAI voice instrumentation cost adapter"""

    def test_tts_cost(self):
        from kalibr.instrumentation.openai_instr import OpenAIVoiceCostAdapter

        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.calculate_cost("tts-1", {"characters": 5000})
        expected = compute_cost_flexible("openai", "tts-1", {"characters": 5000})
        assert cost == expected

    def test_stt_cost(self):
        from kalibr.instrumentation.openai_instr import OpenAIVoiceCostAdapter

        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.calculate_cost("whisper-1", {"audio_seconds": 600.0})
        expected = compute_cost_flexible("openai", "whisper-1", {"audio_seconds": 600.0})
        assert cost == expected

    def test_vendor_name(self):
        from kalibr.instrumentation.openai_instr import OpenAIVoiceCostAdapter

        adapter = OpenAIVoiceCostAdapter()
        assert adapter.get_vendor_name() == "openai"

    def test_is_flexible_adapter(self):
        from kalibr.instrumentation.openai_instr import OpenAIVoiceCostAdapter
        from kalibr.instrumentation.base import FlexibleCostAdapter

        adapter = OpenAIVoiceCostAdapter()
        assert isinstance(adapter, FlexibleCostAdapter)


class TestElevenLabsInstrumentation:
    """Tests for ElevenLabs SDK instrumentation"""

    def test_instrumentation_without_sdk(self):
        from kalibr.instrumentation.elevenlabs_instr import get_instrumentation

        instr = get_instrumentation()
        result = instr.instrument()
        assert isinstance(result, bool)


class TestDeepgramInstrumentation:
    """Tests for Deepgram SDK instrumentation"""

    def test_instrumentation_without_sdk(self):
        from kalibr.instrumentation.deepgram_instr import get_instrumentation

        instr = get_instrumentation()
        result = instr.instrument()
        assert isinstance(result, bool)


class TestAutoInstrumentVoice:
    """Tests for voice auto-instrumentation via registry"""

    def test_elevenlabs_provider_recognized(self):
        from kalibr.instrumentation import auto_instrument

        results = auto_instrument(["elevenlabs"])
        assert "elevenlabs" in results

    def test_deepgram_provider_recognized(self):
        from kalibr.instrumentation import auto_instrument

        results = auto_instrument(["deepgram"])
        assert "deepgram" in results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
