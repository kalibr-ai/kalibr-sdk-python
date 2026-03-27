"""Tests for UNIT_PRICING and compute_cost_flexible().

Tests the unified flexible pricing system that replaced the old
VOICE_PRICING / compute_voice_cost() functions.
"""

import pytest
from kalibr.pricing import UNIT_PRICING, compute_cost_flexible


class TestUnitPricingStructure:
    """Test UNIT_PRICING data structure"""

    def test_elevenlabs_models_exist(self):
        assert "eleven_multilingual_v2" in UNIT_PRICING["elevenlabs"]
        assert "eleven_turbo_v2" in UNIT_PRICING["elevenlabs"]
        assert "eleven_flash_v2_5" in UNIT_PRICING["elevenlabs"]

    def test_openai_voice_models_exist(self):
        assert "tts-1" in UNIT_PRICING["openai"]
        assert "tts-1-hd" in UNIT_PRICING["openai"]
        assert "whisper-1" in UNIT_PRICING["openai"]

    def test_deepgram_models_exist(self):
        assert "nova-2" in UNIT_PRICING["deepgram"]
        assert "aura-asteria-en" in UNIT_PRICING["deepgram"]
        assert "enhanced" in UNIT_PRICING["deepgram"]
        assert "base" in UNIT_PRICING["deepgram"]

    def test_all_entries_have_required_keys(self):
        for vendor, models in UNIT_PRICING.items():
            for model, data in models.items():
                assert "unit" in data, f"Missing unit for {vendor}/{model}"
                assert "price_per_unit" in data, f"Missing price_per_unit for {vendor}/{model}"
                assert data["price_per_unit"] > 0, f"Zero/negative price for {vendor}/{model}"

    def test_unit_types_valid(self):
        valid_types = {"characters", "audio_seconds"}
        for vendor, models in UNIT_PRICING.items():
            for model, data in models.items():
                assert data["unit"] in valid_types, f"Invalid unit for {vendor}/{model}: {data['unit']}"

    def test_elevenlabs_price_conversions(self):
        # $0.30/1K chars → 0.0003 per char
        assert UNIT_PRICING["elevenlabs"]["eleven_multilingual_v2"]["price_per_unit"] == 0.0003
        # $0.15/1K chars → 0.00015
        assert UNIT_PRICING["elevenlabs"]["eleven_turbo_v2"]["price_per_unit"] == 0.00015
        # $0.08/1K chars → 0.00008
        assert UNIT_PRICING["elevenlabs"]["eleven_flash_v2"]["price_per_unit"] == 0.00008

    def test_deepgram_price_conversions(self):
        # $0.0043/min → 0.0000717/sec
        assert UNIT_PRICING["deepgram"]["nova-2"]["price_per_unit"] == 0.0000717
        # $0.0065/1K chars → 0.0000065/char
        assert UNIT_PRICING["deepgram"]["aura-asteria-en"]["price_per_unit"] == 0.0000065

    def test_deepgram_aura_voices_complete(self):
        aura_voices = [
            "aura-asteria-en", "aura-luna-en", "aura-stella-en",
            "aura-athena-en", "aura-hera-en", "aura-orion-en",
            "aura-arcas-en", "aura-perseus-en", "aura-angus-en",
            "aura-orpheus-en", "aura-helios-en", "aura-zeus-en",
        ]
        for voice in aura_voices:
            assert voice in UNIT_PRICING["deepgram"]


class TestComputeCostFlexible:
    """Test compute_cost_flexible()"""

    def test_tts_characters(self):
        # OpenAI TTS-1: 0.000015 per char, 5000 chars
        cost = compute_cost_flexible("openai", "tts-1", {"characters": 5000})
        assert cost == round(0.000015 * 5000, 6)

    def test_tts_hd_more_expensive(self):
        cost_std = compute_cost_flexible("openai", "tts-1", {"characters": 1000})
        cost_hd = compute_cost_flexible("openai", "tts-1-hd", {"characters": 1000})
        assert cost_hd > cost_std

    def test_stt_audio_seconds(self):
        # Whisper-1: 0.0001 per second, 600 seconds (10 min)
        cost = compute_cost_flexible("openai", "whisper-1", {"audio_seconds": 600})
        assert cost == round(0.0001 * 600, 6)

    def test_elevenlabs_characters(self):
        # Multilingual v2: 0.0003 per char, 3000 chars
        cost = compute_cost_flexible("elevenlabs", "eleven_multilingual_v2", {"characters": 3000})
        assert cost == round(0.0003 * 3000, 6)

    def test_deepgram_stt_seconds(self):
        # Nova-2: 0.0000717 per second, 3600 seconds (60 min)
        cost = compute_cost_flexible("deepgram", "nova-2", {"audio_seconds": 3600})
        assert cost == round(0.0000717 * 3600, 6)

    def test_deepgram_tts_characters(self):
        # Aura: 0.0000065 per char, 10000 chars
        cost = compute_cost_flexible("deepgram", "aura-asteria-en", {"characters": 10000})
        assert cost == round(0.0000065 * 10000, 6)

    def test_zero_usage(self):
        cost = compute_cost_flexible("openai", "tts-1", {"characters": 0})
        assert cost == 0.0

    def test_unknown_model_returns_zero(self):
        cost = compute_cost_flexible("openai", "unknown-model", {"characters": 1000})
        assert cost == 0.0

    def test_unknown_vendor_returns_zero(self):
        cost = compute_cost_flexible("unknown-vendor", "some-model", {"characters": 1000})
        assert cost == 0.0

    def test_wrong_unit_type_returns_zero(self):
        # TTS model expects characters, but we pass audio_seconds
        cost = compute_cost_flexible("openai", "tts-1", {"audio_seconds": 60})
        assert cost == 0.0

    def test_cost_rounding(self):
        cost = compute_cost_flexible("openai", "tts-1", {"characters": 1})
        assert len(str(cost).split(".")[-1]) <= 6

    def test_case_insensitive_vendor(self):
        cost1 = compute_cost_flexible("OpenAI", "tts-1", {"characters": 1000})
        cost2 = compute_cost_flexible("openai", "tts-1", {"characters": 1000})
        assert cost1 == cost2

    def test_same_model_same_cost(self):
        cost1 = compute_cost_flexible("openai", "tts-1", {"characters": 1000})
        cost2 = compute_cost_flexible("openai", "tts-1", {"characters": 1000})
        assert cost1 == cost2
