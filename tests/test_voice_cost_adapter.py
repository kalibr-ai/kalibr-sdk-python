"""Tests for voice cost adapter implementations.

Tests ElevenLabsCostAdapter, OpenAIVoiceCostAdapter, DeepgramCostAdapter,
and CostAdapterFactory voice methods — all using compute_cost_flexible().
"""

import pytest
from kalibr.cost_adapter import (
    CostAdapterFactory,
    DeepgramCostAdapter,
    ElevenLabsCostAdapter,
    OpenAIVoiceCostAdapter,
)
from kalibr.pricing import compute_cost_flexible


class TestElevenLabsCostAdapter:
    def test_get_vendor_name(self):
        adapter = ElevenLabsCostAdapter()
        assert adapter.get_vendor_name() == "elevenlabs"

    def test_compute_cost(self):
        adapter = ElevenLabsCostAdapter()
        cost = adapter.compute_cost("eleven_multilingual_v2", characters=3000)
        expected = 0.0003 * 3000
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_turbo(self):
        adapter = ElevenLabsCostAdapter()
        cost = adapter.compute_cost("eleven_turbo_v2", characters=1000)
        expected = 0.00015 * 1000
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_flash(self):
        adapter = ElevenLabsCostAdapter()
        cost = adapter.compute_cost("eleven_flash_v2_5", characters=1000)
        expected = 0.00008 * 1000
        assert abs(cost - expected) < 0.000001

    def test_zero_characters(self):
        adapter = ElevenLabsCostAdapter()
        cost = adapter.compute_cost("eleven_multilingual_v2", characters=0)
        assert cost == 0.0


class TestOpenAIVoiceCostAdapter:
    def test_get_vendor_name(self):
        adapter = OpenAIVoiceCostAdapter()
        assert adapter.get_vendor_name() == "openai"

    def test_tts_cost(self):
        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.compute_cost("tts-1", characters=5000)
        expected = 0.000015 * 5000
        assert abs(cost - expected) < 0.000001

    def test_tts_hd_cost(self):
        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.compute_cost("tts-1-hd", characters=2000)
        expected = 0.00003 * 2000
        assert abs(cost - expected) < 0.000001

    def test_stt_cost(self):
        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.compute_cost("whisper-1", audio_seconds=600.0)
        expected = 0.0001 * 600
        assert abs(cost - expected) < 0.000001

    def test_zero_usage(self):
        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.compute_cost("tts-1", characters=0)
        assert cost == 0.0


class TestDeepgramCostAdapter:
    def test_get_vendor_name(self):
        adapter = DeepgramCostAdapter()
        assert adapter.get_vendor_name() == "deepgram"

    def test_stt_cost(self):
        adapter = DeepgramCostAdapter()
        # 60 min = 3600 seconds
        cost = adapter.compute_cost("nova-2", audio_seconds=3600.0)
        expected = 0.0000717 * 3600
        assert abs(cost - expected) < 0.000001

    def test_tts_cost(self):
        adapter = DeepgramCostAdapter()
        cost = adapter.compute_cost("aura-asteria-en", characters=1000)
        expected = 0.0000065 * 1000
        assert abs(cost - expected) < 0.000001

    def test_zero_duration(self):
        adapter = DeepgramCostAdapter()
        cost = adapter.compute_cost("nova-2", audio_seconds=0.0)
        assert cost == 0.0


class TestCostAdapterFactoryVoice:
    def test_compute_voice_cost_via_factory(self):
        cost = CostAdapterFactory.compute_voice_cost(
            "openai", "tts-1", characters=5000
        )
        expected = 0.000015 * 5000
        assert abs(cost - expected) < 0.000001

    def test_compute_voice_cost_unknown_vendor(self):
        cost = CostAdapterFactory.compute_voice_cost(
            "unknown-vendor", "some-model", characters=1000
        )
        assert cost == 0.0


class TestVoiceAdapterConsistency:
    """Test consistency between voice adapters and compute_cost_flexible"""

    def test_openai_voice_adapter_matches_flexible(self):
        adapter = OpenAIVoiceCostAdapter()
        adapter_cost = adapter.compute_cost("tts-1", characters=5000)
        flexible_cost = compute_cost_flexible("openai", "tts-1", {"characters": 5000})
        assert adapter_cost == flexible_cost

    def test_elevenlabs_adapter_matches_flexible(self):
        adapter = ElevenLabsCostAdapter()
        adapter_cost = adapter.compute_cost("eleven_multilingual_v2", characters=3000)
        flexible_cost = compute_cost_flexible(
            "elevenlabs", "eleven_multilingual_v2", {"characters": 3000}
        )
        assert adapter_cost == flexible_cost

    def test_deepgram_adapter_matches_flexible(self):
        adapter = DeepgramCostAdapter()
        adapter_cost = adapter.compute_cost("nova-2", audio_seconds=600.0)
        flexible_cost = compute_cost_flexible(
            "deepgram", "nova-2", {"audio_seconds": 600.0}
        )
        assert adapter_cost == flexible_cost
