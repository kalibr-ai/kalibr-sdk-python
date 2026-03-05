"""Tests for voice pricing module.

Tests VOICE_PRICING structure, get_voice_pricing(), compute_voice_cost(),
and normalize_voice_model_name().
"""

import pytest
from kalibr.pricing import (
    VOICE_PRICING,
    VOICE_DEFAULT_PRICING,
    get_voice_pricing,
    compute_voice_cost,
    normalize_voice_model_name,
)


class TestVoicePricingStructure:
    """Test voice pricing data structure"""

    def test_vendors_exist(self):
        assert "elevenlabs" in VOICE_PRICING
        assert "openai" in VOICE_PRICING
        assert "deepgram" in VOICE_PRICING

    def test_elevenlabs_models(self):
        models = VOICE_PRICING["elevenlabs"]
        assert "eleven_multilingual_v2" in models
        assert "eleven_turbo_v2" in models
        assert "eleven_flash_v2_5" in models
        for model, data in models.items():
            assert "unit" in data
            assert "price" in data
            assert data["unit"] == "per_1k_chars"
            assert data["price"] > 0

    def test_openai_voice_models(self):
        models = VOICE_PRICING["openai"]
        assert "tts-1" in models
        assert "tts-1-hd" in models
        assert "whisper-1" in models
        assert models["tts-1"]["unit"] == "per_1k_chars"
        assert models["whisper-1"]["unit"] == "per_minute"

    def test_deepgram_models(self):
        models = VOICE_PRICING["deepgram"]
        assert "nova-2" in models
        assert "aura-asteria-en" in models
        assert models["nova-2"]["unit"] == "per_minute"
        assert models["aura-asteria-en"]["unit"] == "per_1k_chars"

    def test_default_pricing_exists(self):
        assert "elevenlabs" in VOICE_DEFAULT_PRICING
        assert "openai" in VOICE_DEFAULT_PRICING
        assert "deepgram" in VOICE_DEFAULT_PRICING


class TestNormalizeVoiceModelName:
    """Test voice model name normalization"""

    def test_exact_match(self):
        assert normalize_voice_model_name("openai", "tts-1") == "tts-1"
        assert normalize_voice_model_name("openai", "whisper-1") == "whisper-1"
        assert normalize_voice_model_name("deepgram", "nova-2") == "nova-2"

    def test_openai_fuzzy(self):
        assert normalize_voice_model_name("openai", "tts-1-hd-latest") == "tts-1-hd"
        assert normalize_voice_model_name("openai", "tts-model") == "tts-1"
        assert normalize_voice_model_name("openai", "whisper-large") == "whisper-1"

    def test_elevenlabs_fuzzy(self):
        assert normalize_voice_model_name("elevenlabs", "eleven_flash_v2_5") == "eleven_flash_v2_5"
        result = normalize_voice_model_name("elevenlabs", "flash-model")
        assert "flash" in result

    def test_deepgram_fuzzy(self):
        assert normalize_voice_model_name("deepgram", "nova-2-general") == "nova-2-general"
        assert normalize_voice_model_name("deepgram", "nova-2-custom") == "nova-2"
        assert normalize_voice_model_name("deepgram", "nova-1") == "nova"

    def test_case_insensitive(self):
        assert normalize_voice_model_name("openai", "TTS-1") == "tts-1"
        assert normalize_voice_model_name("openai", "WHISPER-1") == "whisper-1"

    def test_unknown_returns_lowercase(self):
        assert normalize_voice_model_name("openai", "unknown-voice") == "unknown-voice"


class TestGetVoicePricing:
    """Test voice pricing retrieval"""

    def test_openai_tts(self):
        pricing, normalized = get_voice_pricing("openai", "tts-1")
        assert pricing["unit"] == "per_1k_chars"
        assert pricing["price"] == 0.015
        assert normalized == "tts-1"

    def test_openai_tts_hd(self):
        pricing, normalized = get_voice_pricing("openai", "tts-1-hd")
        assert pricing["price"] == 0.030
        assert normalized == "tts-1-hd"

    def test_openai_whisper(self):
        pricing, normalized = get_voice_pricing("openai", "whisper-1")
        assert pricing["unit"] == "per_minute"
        assert pricing["price"] == 0.006

    def test_elevenlabs_multilingual(self):
        pricing, normalized = get_voice_pricing("elevenlabs", "eleven_multilingual_v2")
        assert pricing["price"] == 0.30
        assert pricing["unit"] == "per_1k_chars"

    def test_deepgram_nova2(self):
        pricing, normalized = get_voice_pricing("deepgram", "nova-2")
        assert pricing["unit"] == "per_minute"
        assert pricing["price"] == 0.0043

    def test_unknown_model_fallback(self):
        pricing, _ = get_voice_pricing("openai", "unknown-voice-model")
        assert "unit" in pricing
        assert "price" in pricing
        assert pricing["price"] > 0

    def test_unknown_vendor_fallback(self):
        pricing, _ = get_voice_pricing("unknown-vendor", "some-model")
        assert "unit" in pricing
        assert "price" in pricing


class TestComputeVoiceCost:
    """Test voice cost computation"""

    def test_tts_cost(self):
        # OpenAI TTS-1: $0.015 per 1K chars
        cost = compute_voice_cost("openai", "tts-1", characters=5000)
        expected = (5000 / 1_000) * 0.015
        assert abs(cost - expected) < 0.000001
        assert cost == 0.075

    def test_tts_hd_cost(self):
        # OpenAI TTS-1-HD: $0.030 per 1K chars
        cost = compute_voice_cost("openai", "tts-1-hd", characters=2000)
        expected = (2000 / 1_000) * 0.030
        assert abs(cost - expected) < 0.000001
        assert cost == 0.06

    def test_stt_cost(self):
        # Whisper-1: $0.006 per minute
        cost = compute_voice_cost("openai", "whisper-1", audio_duration_minutes=10.0)
        expected = 10.0 * 0.006
        assert abs(cost - expected) < 0.000001
        assert cost == 0.06

    def test_elevenlabs_cost(self):
        # ElevenLabs multilingual v2: $0.30 per 1K chars
        cost = compute_voice_cost("elevenlabs", "eleven_multilingual_v2", characters=3000)
        expected = (3000 / 1_000) * 0.30
        assert abs(cost - expected) < 0.000001
        assert cost == 0.9

    def test_deepgram_stt_cost(self):
        # Deepgram Nova-2: $0.0043 per minute
        cost = compute_voice_cost("deepgram", "nova-2", audio_duration_minutes=60.0)
        expected = 60.0 * 0.0043
        assert abs(cost - expected) < 0.000001
        assert cost == 0.258

    def test_zero_usage(self):
        cost = compute_voice_cost("openai", "tts-1", characters=0)
        assert cost == 0.0

    def test_zero_duration(self):
        cost = compute_voice_cost("openai", "whisper-1", audio_duration_minutes=0.0)
        assert cost == 0.0

    def test_cost_rounding(self):
        cost = compute_voice_cost("openai", "tts-1", characters=1)
        assert len(str(cost).split(".")[-1]) <= 6


class TestVoicePricingConsistency:
    """Test consistency in voice pricing"""

    def test_same_model_same_cost(self):
        cost1 = compute_voice_cost("openai", "tts-1", characters=1000)
        cost2 = compute_voice_cost("openai", "tts-1", characters=1000)
        assert cost1 == cost2

    def test_tts_hd_more_expensive(self):
        cost_std = compute_voice_cost("openai", "tts-1", characters=1000)
        cost_hd = compute_voice_cost("openai", "tts-1-hd", characters=1000)
        assert cost_hd > cost_std
