"""Tests for voice SDK instrumentation.

Tests ElevenLabs, Deepgram, and OpenAI audio instrumentation
using mocked SDKs.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestElevenLabsCostAdapter:
    """Tests for ElevenLabs instrumentation cost adapter"""

    def test_cost_calculation(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter

        adapter = ElevenLabsCostAdapter()
        cost = adapter.calculate_cost(
            "eleven_multilingual_v2", {"characters": 3000}
        )
        expected = (3000 / 1_000) * 0.30
        assert abs(cost - expected) < 0.000001

    def test_cost_calculation_turbo(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter

        adapter = ElevenLabsCostAdapter()
        cost = adapter.calculate_cost(
            "eleven_turbo_v2", {"characters": 1000}
        )
        expected = (1000 / 1_000) * 0.15
        assert abs(cost - expected) < 0.000001

    def test_zero_characters(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter

        adapter = ElevenLabsCostAdapter()
        cost = adapter.calculate_cost("eleven_multilingual_v2", {"characters": 0})
        assert cost == 0.0

    def test_vendor_name(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter

        adapter = ElevenLabsCostAdapter()
        assert adapter.get_vendor_name() == "elevenlabs"


class TestDeepgramCostAdapter:
    """Tests for Deepgram instrumentation cost adapter"""

    def test_cost_calculation_stt(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter

        adapter = DeepgramCostAdapter()
        cost = adapter.calculate_cost(
            "nova-2", {"audio_duration_minutes": 10.0}
        )
        expected = 10.0 * 0.0043
        assert abs(cost - expected) < 0.000001

    def test_cost_calculation_tts(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter

        adapter = DeepgramCostAdapter()
        cost = adapter.calculate_cost(
            "aura-asteria-en", {"characters": 1000}
        )
        expected = (1000 / 1_000) * 0.0065
        assert abs(cost - expected) < 0.000001

    def test_zero_duration(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter

        adapter = DeepgramCostAdapter()
        cost = adapter.calculate_cost("nova-2", {"audio_duration_minutes": 0.0})
        assert cost == 0.0

    def test_vendor_name(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter

        adapter = DeepgramCostAdapter()
        assert adapter.get_vendor_name() == "deepgram"


class TestOpenAIVoiceCostAdapter:
    """Tests for OpenAI voice instrumentation cost adapter"""

    def test_tts_cost(self):
        from kalibr.instrumentation.openai_instr import OpenAIVoiceCostAdapter

        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.calculate_cost("tts-1", {"characters": 5000})
        expected = (5000 / 1_000) * 0.015
        assert abs(cost - expected) < 0.000001

    def test_stt_cost(self):
        from kalibr.instrumentation.openai_instr import OpenAIVoiceCostAdapter

        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.calculate_cost("whisper-1", {"audio_duration_minutes": 10.0})
        expected = 10.0 * 0.006
        assert abs(cost - expected) < 0.000001

    def test_vendor_name(self):
        from kalibr.instrumentation.openai_instr import OpenAIVoiceCostAdapter

        adapter = OpenAIVoiceCostAdapter()
        assert adapter.get_vendor_name() == "openai"


class TestElevenLabsInstrumentation:
    """Tests for ElevenLabs SDK instrumentation"""

    def test_instrumentation_without_sdk(self):
        """Instrumentation should handle missing SDK gracefully"""
        from kalibr.instrumentation.elevenlabs_instr import get_instrumentation

        instr = get_instrumentation()
        # May return False if elevenlabs not installed
        result = instr.instrument()
        assert isinstance(result, bool)


class TestDeepgramInstrumentation:
    """Tests for Deepgram SDK instrumentation"""

    def test_instrumentation_without_sdk(self):
        """Instrumentation should handle missing SDK gracefully"""
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
        # May be False if SDK not installed, but should not raise

    def test_deepgram_provider_recognized(self):
        from kalibr.instrumentation import auto_instrument

        results = auto_instrument(["deepgram"])
        assert "deepgram" in results


class TestVoiceCostConsistency:
    """Test consistency between voice instrumentation adapters and centralized pricing"""

    def test_elevenlabs_instr_matches_pricing(self):
        from kalibr.instrumentation.elevenlabs_instr import ElevenLabsCostAdapter
        from kalibr.pricing import compute_voice_cost

        adapter = ElevenLabsCostAdapter()
        adapter_cost = adapter.calculate_cost(
            "eleven_multilingual_v2", {"characters": 3000}
        )
        pricing_cost = compute_voice_cost(
            "elevenlabs", "eleven_multilingual_v2", characters=3000
        )
        assert adapter_cost == pricing_cost

    def test_deepgram_instr_matches_pricing(self):
        from kalibr.instrumentation.deepgram_instr import DeepgramCostAdapter
        from kalibr.pricing import compute_voice_cost

        adapter = DeepgramCostAdapter()
        adapter_cost = adapter.calculate_cost(
            "nova-2", {"audio_duration_minutes": 10.0}
        )
        pricing_cost = compute_voice_cost(
            "deepgram", "nova-2", audio_duration_minutes=10.0
        )
        assert adapter_cost == pricing_cost

    def test_openai_voice_instr_matches_pricing(self):
        from kalibr.instrumentation.openai_instr import OpenAIVoiceCostAdapter
        from kalibr.pricing import compute_voice_cost

        adapter = OpenAIVoiceCostAdapter()
        adapter_cost = adapter.calculate_cost("tts-1", {"characters": 5000})
        pricing_cost = compute_voice_cost("openai", "tts-1", characters=5000)
        assert adapter_cost == pricing_cost


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
