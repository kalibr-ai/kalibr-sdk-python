"""Tests for TraceEvent model - backwards compatibility and non-LLM support."""

import pytest
from datetime import datetime, timezone

from kalibr.trace_models import KNOWN_PROVIDERS, TraceEvent


# Minimal valid kwargs shared across tests
def _base_kwargs(**overrides):
    base = {
        "schema_version": "1.0",
        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
        "span_id": "a1b2c3d4-e5f6-47a8-b9c0-123456789abc",
        "tenant_id": "acme-corp",
        "provider": "openai",
        "model_id": "gpt-4o",
        "operation": "chat_completion",
        "duration_ms": 250,
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.000375,
        "status": "success",
        "timestamp": datetime(2025, 10, 30, 12, 0, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


# ---- Backwards compatibility ----

class TestBackwardsCompatibility:
    """All existing TraceEvent construction patterns must still work."""

    def test_existing_construction_with_tokens(self):
        event = TraceEvent(**_base_kwargs())
        assert event.input_tokens == 100
        assert event.output_tokens == 50
        assert event.total_tokens == 150
        assert event.provider == "openai"

    def test_old_format_dict_roundtrip(self):
        """Old-format dict -> TraceEvent -> dict still works."""
        data = _base_kwargs()
        event = TraceEvent(**data)
        dumped = event.model_dump()
        assert dumped["input_tokens"] == 100
        assert dumped["output_tokens"] == 50
        assert dumped["provider"] == "openai"

    def test_all_original_providers(self):
        for provider in ["openai", "anthropic", "google", "cohere", "custom"]:
            event = TraceEvent(**_base_kwargs(provider=provider))
            assert event.provider == provider

    def test_legacy_fields_still_synced(self):
        event = TraceEvent(**_base_kwargs())
        assert event.latency_ms == event.duration_ms
        assert event.total_cost_usd == event.cost_usd
        assert event.vendor == event.provider

    def test_new_optional_fields_absent_in_old_construction(self):
        """Old construction doesn't set new fields."""
        event = TraceEvent(**_base_kwargs())
        assert event.audio_duration_ms is None
        assert event.audio_format is None
        assert event.image_count is None
        assert event.image_resolution is None
        assert event.input_units is None
        assert event.output_units is None
        assert event.modality is None
        assert event.task_type is None

    def test_unit_type_auto_set_when_tokens_present(self):
        event = TraceEvent(**_base_kwargs())
        assert event.unit_type == "tokens"

    def test_serialization_unchanged_for_old_events(self):
        """JSON serialization still includes all original fields."""
        event = TraceEvent(**_base_kwargs())
        json_data = event.model_dump(mode="json")
        required_keys = {
            "schema_version", "trace_id", "span_id", "tenant_id",
            "provider", "model_id", "operation", "duration_ms",
            "input_tokens", "output_tokens", "cost_usd", "status", "timestamp",
        }
        assert required_keys.issubset(json_data.keys())


# ---- Provider field changes ----

class TestProviderField:
    """Provider is now a free-form str with length constraints."""

    def test_new_providers(self):
        for provider in ["huggingface", "elevenlabs", "deepgram"]:
            event = TraceEvent(**_base_kwargs(provider=provider))
            assert event.provider == provider

    def test_arbitrary_provider(self):
        event = TraceEvent(**_base_kwargs(provider="my-custom-provider"))
        assert event.provider == "my-custom-provider"

    def test_empty_provider_rejected(self):
        with pytest.raises(Exception):
            TraceEvent(**_base_kwargs(provider=""))

    def test_too_long_provider_rejected(self):
        with pytest.raises(Exception):
            TraceEvent(**_base_kwargs(provider="x" * 33))

    def test_known_providers_constant(self):
        assert "openai" in KNOWN_PROVIDERS
        assert "huggingface" in KNOWN_PROVIDERS
        assert "elevenlabs" in KNOWN_PROVIDERS
        assert "deepgram" in KNOWN_PROVIDERS


# ---- Token defaults ----

class TestTokenDefaults:
    """input_tokens and output_tokens now default to 0."""

    def test_tokens_default_to_zero(self):
        kwargs = _base_kwargs()
        del kwargs["input_tokens"]
        del kwargs["output_tokens"]
        event = TraceEvent(**kwargs)
        assert event.input_tokens == 0
        assert event.output_tokens == 0
        assert event.total_tokens == 0

    def test_explicit_tokens_still_work(self):
        event = TraceEvent(**_base_kwargs(input_tokens=500, output_tokens=200))
        assert event.input_tokens == 500
        assert event.output_tokens == 200
        assert event.total_tokens == 700


# ---- Audio metrics ----

class TestAudioMetrics:
    def test_audio_event(self):
        event = TraceEvent(**_base_kwargs(
            provider="elevenlabs",
            model_id="eleven_multilingual_v2",
            operation="text_to_speech",
            input_tokens=0,
            output_tokens=0,
            audio_duration_ms=5000,
            audio_format="mp3",
            modality="audio",
            task_type="text-to-speech",
        ))
        assert event.audio_duration_ms == 5000
        assert event.audio_format == "mp3"
        assert event.modality == "audio"
        assert event.task_type == "text-to-speech"

    def test_audio_without_tokens(self):
        kwargs = _base_kwargs(
            provider="deepgram",
            model_id="nova-2",
            operation="transcription",
            audio_duration_ms=30000,
            audio_format="wav",
        )
        del kwargs["input_tokens"]
        del kwargs["output_tokens"]
        event = TraceEvent(**kwargs)
        assert event.input_tokens == 0
        assert event.output_tokens == 0
        assert event.audio_duration_ms == 30000

    def test_audio_format_max_length(self):
        with pytest.raises(Exception):
            TraceEvent(**_base_kwargs(audio_format="x" * 17))


# ---- Image metrics ----

class TestImageMetrics:
    def test_image_event(self):
        event = TraceEvent(**_base_kwargs(
            provider="openai",
            model_id="dall-e-3",
            operation="image_generation",
            input_tokens=0,
            output_tokens=0,
            image_count=2,
            image_resolution="1024x1024",
            modality="image",
        ))
        assert event.image_count == 2
        assert event.image_resolution == "1024x1024"
        assert event.modality == "image"

    def test_image_count_validation(self):
        with pytest.raises(Exception):
            TraceEvent(**_base_kwargs(image_count=-1))


# ---- Generic units ----

class TestGenericUnits:
    def test_custom_units(self):
        event = TraceEvent(**_base_kwargs(
            input_units=1500.0,
            output_units=0.0,
            unit_type="characters",
        ))
        assert event.input_units == 1500.0
        assert event.unit_type == "characters"

    def test_unit_type_not_overridden_when_explicit(self):
        event = TraceEvent(**_base_kwargs(unit_type="audio_seconds"))
        assert event.unit_type == "audio_seconds"

    def test_unit_type_auto_tokens_when_tokens_present(self):
        event = TraceEvent(**_base_kwargs(input_tokens=10, output_tokens=0))
        assert event.unit_type == "tokens"

    def test_unit_type_none_when_no_tokens(self):
        kwargs = _base_kwargs()
        del kwargs["input_tokens"]
        del kwargs["output_tokens"]
        event = TraceEvent(**kwargs)
        assert event.unit_type is None


# ---- Extra fields still rejected ----

class TestExtraFieldsRejected:
    def test_unknown_field_rejected(self):
        with pytest.raises(Exception):
            TraceEvent(**_base_kwargs(bogus_field="should fail"))
