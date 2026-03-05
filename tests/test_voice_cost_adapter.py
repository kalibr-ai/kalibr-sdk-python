"""Tests for voice cost adapter implementations.

Tests ElevenLabsCostAdapter, OpenAIVoiceCostAdapter, DeepgramCostAdapter,
and CostAdapterFactory voice methods.
"""

import pytest
from kalibr.cost_adapter import (
    BaseVoiceCostAdapter,
    CostAdapterFactory,
    DeepgramCostAdapter,
    ElevenLabsCostAdapter,
    OpenAIVoiceCostAdapter,
)


class TestElevenLabsCostAdapter:
    def test_get_vendor_name(self):
        adapter = ElevenLabsCostAdapter()
        assert adapter.get_vendor_name() == "elevenlabs"

    def test_compute_cost(self):
        adapter = ElevenLabsCostAdapter()
        cost = adapter.compute_cost("eleven_multilingual_v2", characters=3000)
        expected = (3000 / 1_000) * 0.30
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_turbo(self):
        adapter = ElevenLabsCostAdapter()
        cost = adapter.compute_cost("eleven_turbo_v2", characters=1000)
        expected = (1000 / 1_000) * 0.15
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_flash(self):
        adapter = ElevenLabsCostAdapter()
        cost = adapter.compute_cost("eleven_flash_v2_5", characters=1000)
        expected = (1000 / 1_000) * 0.08
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
        expected = (5000 / 1_000) * 0.015
        assert abs(cost - expected) < 0.000001

    def test_tts_hd_cost(self):
        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.compute_cost("tts-1-hd", characters=2000)
        expected = (2000 / 1_000) * 0.030
        assert abs(cost - expected) < 0.000001

    def test_stt_cost(self):
        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.compute_cost("whisper-1", audio_duration_minutes=10.0)
        expected = 10.0 * 0.006
        assert abs(cost - expected) < 0.000001

    def test_zero_usage(self):
        adapter = OpenAIVoiceCostAdapter()
        cost = adapter.compute_cost("tts-1", characters=0, audio_duration_minutes=0.0)
        assert cost == 0.0


class TestDeepgramCostAdapter:
    def test_get_vendor_name(self):
        adapter = DeepgramCostAdapter()
        assert adapter.get_vendor_name() == "deepgram"

    def test_stt_cost(self):
        adapter = DeepgramCostAdapter()
        cost = adapter.compute_cost("nova-2", audio_duration_minutes=60.0)
        expected = 60.0 * 0.0043
        assert abs(cost - expected) < 0.000001

    def test_tts_cost(self):
        adapter = DeepgramCostAdapter()
        cost = adapter.compute_cost("aura-asteria-en", characters=1000)
        expected = (1000 / 1_000) * 0.0065
        assert abs(cost - expected) < 0.000001

    def test_zero_duration(self):
        adapter = DeepgramCostAdapter()
        cost = adapter.compute_cost("nova-2", audio_duration_minutes=0.0)
        assert cost == 0.0


class TestCostAdapterFactoryVoice:
    def test_get_voice_adapter_elevenlabs(self):
        adapter = CostAdapterFactory.get_voice_adapter("elevenlabs")
        assert adapter is not None
        assert isinstance(adapter, ElevenLabsCostAdapter)

    def test_get_voice_adapter_openai(self):
        adapter = CostAdapterFactory.get_voice_adapter("openai")
        assert adapter is not None
        assert isinstance(adapter, OpenAIVoiceCostAdapter)

    def test_get_voice_adapter_deepgram(self):
        adapter = CostAdapterFactory.get_voice_adapter("deepgram")
        assert adapter is not None
        assert isinstance(adapter, DeepgramCostAdapter)

    def test_get_voice_adapter_case_insensitive(self):
        adapter = CostAdapterFactory.get_voice_adapter("ElevenLabs")
        assert adapter is not None

    def test_get_voice_adapter_unknown(self):
        adapter = CostAdapterFactory.get_voice_adapter("unknown-vendor")
        assert adapter is None

    def test_compute_voice_cost_via_factory(self):
        cost = CostAdapterFactory.compute_voice_cost(
            "openai", "tts-1", characters=5000
        )
        expected = (5000 / 1_000) * 0.015
        assert abs(cost - expected) < 0.000001

    def test_compute_voice_cost_unknown_vendor(self):
        cost = CostAdapterFactory.compute_voice_cost(
            "unknown-vendor", "some-model", characters=1000
        )
        assert cost == 0.0

    def test_register_custom_voice_adapter(self):
        class CustomVoiceAdapter(BaseVoiceCostAdapter):
            def get_vendor_name(self):
                return "custom"

            def compute_cost(self, model_name, characters=0, audio_duration_minutes=0.0):
                return 0.42

        CostAdapterFactory.register_voice_adapter("custom_voice", CustomVoiceAdapter())
        adapter = CostAdapterFactory.get_voice_adapter("custom_voice")
        assert adapter is not None
        assert adapter.compute_cost("any-model") == 0.42


class TestVoiceAdapterConsistency:
    """Test consistency between voice adapters and centralized pricing"""

    def test_openai_voice_adapter_matches_pricing(self):
        from kalibr.pricing import compute_voice_cost as pricing_compute

        adapter = OpenAIVoiceCostAdapter()
        adapter_cost = adapter.compute_cost("tts-1", characters=5000)
        pricing_cost = pricing_compute("openai", "tts-1", characters=5000)
        assert adapter_cost == pricing_cost

    def test_elevenlabs_adapter_matches_pricing(self):
        from kalibr.pricing import compute_voice_cost as pricing_compute

        adapter = ElevenLabsCostAdapter()
        adapter_cost = adapter.compute_cost("eleven_multilingual_v2", characters=3000)
        pricing_cost = pricing_compute("elevenlabs", "eleven_multilingual_v2", characters=3000)
        assert adapter_cost == pricing_cost

    def test_deepgram_adapter_matches_pricing(self):
        from kalibr.pricing import compute_voice_cost as pricing_compute

        adapter = DeepgramCostAdapter()
        adapter_cost = adapter.compute_cost("nova-2", audio_duration_minutes=10.0)
        pricing_cost = pricing_compute("deepgram", "nova-2", audio_duration_minutes=10.0)
        assert adapter_cost == pricing_cost
