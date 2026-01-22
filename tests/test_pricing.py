"""Tests for centralized pricing module.

Tests pricing retrieval, model name normalization, and cost calculations
to ensure consistency across all adapters.
"""

import pytest
from kalibr.pricing import (
    MODEL_PRICING,
    PRICING_VERSION,
    compute_cost,
    get_pricing,
    normalize_model_name,
)


class TestPricingVersion:
    """Test pricing version metadata"""

    def test_pricing_version_exists(self):
        """Test that pricing version is defined"""
        assert PRICING_VERSION is not None
        assert isinstance(PRICING_VERSION, str)
        assert len(PRICING_VERSION) > 0


class TestModelPricing:
    """Test model pricing data structure"""

    def test_pricing_structure(self):
        """Test that pricing data has correct structure"""
        assert "openai" in MODEL_PRICING
        assert "anthropic" in MODEL_PRICING
        assert "google" in MODEL_PRICING

    def test_openai_models(self):
        """Test that OpenAI models have pricing"""
        openai_pricing = MODEL_PRICING["openai"]
        expected_models = [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo",
        ]
        for model in expected_models:
            assert model in openai_pricing
            assert "input" in openai_pricing[model]
            assert "output" in openai_pricing[model]
            assert openai_pricing[model]["input"] > 0
            assert openai_pricing[model]["output"] > 0

    def test_anthropic_models(self):
        """Test that Anthropic models have pricing"""
        anthropic_pricing = MODEL_PRICING["anthropic"]
        expected_models = [
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "claude-3-5-sonnet",
        ]
        for model in expected_models:
            assert model in anthropic_pricing
            assert "input" in anthropic_pricing[model]
            assert "output" in anthropic_pricing[model]
            assert anthropic_pricing[model]["input"] > 0
            assert anthropic_pricing[model]["output"] > 0

    def test_google_models(self):
        """Test that Google models have pricing"""
        google_pricing = MODEL_PRICING["google"]
        expected_models = [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-pro",
        ]
        for model in expected_models:
            assert model in google_pricing
            assert "input" in google_pricing[model]
            assert "output" in google_pricing[model]
            assert google_pricing[model]["input"] > 0
            assert google_pricing[model]["output"] > 0


class TestNormalizeModelName:
    """Test model name normalization"""

    def test_openai_exact_match(self):
        """Test exact match for OpenAI models"""
        assert normalize_model_name("openai", "gpt-4o") == "gpt-4o"
        assert normalize_model_name("openai", "gpt-4") == "gpt-4"
        assert normalize_model_name("openai", "gpt-4o-mini") == "gpt-4o-mini"

    def test_openai_date_suffix_removal(self):
        """Test OpenAI models with date suffixes"""
        assert normalize_model_name("openai", "gpt-4o-2024-05-13") == "gpt-4o"
        assert normalize_model_name("openai", "gpt-4-turbo-2024-04-09") == "gpt-4-turbo"
        assert normalize_model_name("openai", "gpt-3.5-turbo-2024-01-01") == "gpt-3.5-turbo"

    def test_openai_fuzzy_matching(self):
        """Test fuzzy matching for OpenAI models"""
        assert normalize_model_name("openai", "gpt-4o-mini-preview") == "gpt-4o-mini"
        assert normalize_model_name("openai", "gpt-4o-preview") == "gpt-4o"
        assert normalize_model_name("openai", "gpt-4-turbo-preview") == "gpt-4-turbo"

    def test_anthropic_exact_match(self):
        """Test exact match for Anthropic models"""
        assert normalize_model_name("anthropic", "claude-3-opus") == "claude-3-opus"
        assert normalize_model_name("anthropic", "claude-3-5-sonnet") == "claude-3-5-sonnet"
        assert normalize_model_name("anthropic", "claude-3-haiku") == "claude-3-haiku"

    def test_anthropic_date_suffix(self):
        """Test Anthropic models with date suffixes"""
        assert (
            normalize_model_name("anthropic", "claude-3-5-sonnet-20240620")
            == "claude-3-5-sonnet"
        )
        assert (
            normalize_model_name("anthropic", "claude-3-opus-20240229") == "claude-3-opus"
        )

    def test_anthropic_fuzzy_matching(self):
        """Test fuzzy matching for Anthropic models"""
        # Test alternate naming conventions
        assert normalize_model_name("anthropic", "claude-3.5-sonnet") == "claude-3-5-sonnet"

    def test_google_exact_match(self):
        """Test exact match for Google models"""
        assert normalize_model_name("google", "gemini-1.5-pro") == "gemini-1.5-pro"
        assert normalize_model_name("google", "gemini-1.5-flash") == "gemini-1.5-flash"
        assert normalize_model_name("google", "gemini-pro") == "gemini-pro"

    def test_google_fuzzy_matching(self):
        """Test fuzzy matching for Google models"""
        assert normalize_model_name("google", "gemini-1.5-pro-latest") == "gemini-1.5-pro"
        assert normalize_model_name("google", "gemini-1.5-flash-latest") == "gemini-1.5-flash"

    def test_case_insensitive(self):
        """Test that normalization is case-insensitive"""
        assert normalize_model_name("openai", "GPT-4O") == "gpt-4o"
        assert normalize_model_name("anthropic", "CLAUDE-3-OPUS") == "claude-3-opus"
        assert normalize_model_name("google", "GEMINI-PRO") == "gemini-pro"

    def test_unknown_model_returns_original(self):
        """Test that unknown models return normalized version of original"""
        result = normalize_model_name("openai", "unknown-model")
        assert result == "unknown-model"


class TestGetPricing:
    """Test pricing retrieval"""

    def test_openai_pricing(self):
        """Test getting OpenAI pricing"""
        pricing, normalized = get_pricing("openai", "gpt-4o")
        assert pricing["input"] == 2.50
        assert pricing["output"] == 10.00
        assert normalized == "gpt-4o"

    def test_anthropic_pricing(self):
        """Test getting Anthropic pricing"""
        pricing, normalized = get_pricing("anthropic", "claude-3-opus")
        assert pricing["input"] == 15.00
        assert pricing["output"] == 75.00
        assert normalized == "claude-3-opus"

    def test_google_pricing(self):
        """Test getting Google pricing"""
        pricing, normalized = get_pricing("google", "gemini-1.5-pro")
        assert pricing["input"] == 1.25
        assert pricing["output"] == 5.00
        assert normalized == "gemini-1.5-pro"

    def test_pricing_with_date_suffix(self):
        """Test pricing retrieval with date suffixes"""
        pricing, normalized = get_pricing("openai", "gpt-4o-2024-05-13")
        assert pricing["input"] == 2.50
        assert pricing["output"] == 10.00
        assert normalized == "gpt-4o"

    def test_unknown_model_fallback(self):
        """Test that unknown models fall back to default pricing"""
        pricing, _ = get_pricing("openai", "unknown-model")
        # Should fall back to GPT-4 pricing (highest tier)
        assert pricing["input"] == 30.00
        assert pricing["output"] == 60.00

    def test_unknown_vendor_fallback(self):
        """Test that unknown vendors fall back to safe default"""
        pricing, _ = get_pricing("unknown-vendor", "some-model")
        # Should have some default pricing
        assert "input" in pricing
        assert "output" in pricing
        assert pricing["input"] > 0
        assert pricing["output"] > 0


class TestComputeCost:
    """Test cost computation"""

    def test_openai_cost_calculation(self):
        """Test OpenAI cost calculation"""
        # GPT-4o: $2.50/1M input, $10.00/1M output
        # 1000 input, 500 output tokens
        cost = compute_cost("openai", "gpt-4o", 1000, 500)
        expected = (1000 / 1_000_000 * 2.50) + (500 / 1_000_000 * 10.00)
        assert abs(cost - expected) < 0.000001
        assert cost == 0.0075

    def test_anthropic_cost_calculation(self):
        """Test Anthropic cost calculation"""
        # Claude-3-sonnet: $3.00/1M input, $15.00/1M output
        # 2000 input, 1000 output tokens
        cost = compute_cost("anthropic", "claude-3-sonnet", 2000, 1000)
        expected = (2000 / 1_000_000 * 3.00) + (1000 / 1_000_000 * 15.00)
        assert abs(cost - expected) < 0.000001
        assert cost == 0.021

    def test_google_cost_calculation(self):
        """Test Google cost calculation"""
        # Gemini-1.5-pro: $1.25/1M input, $5.00/1M output
        # 5000 input, 2500 output tokens
        cost = compute_cost("google", "gemini-1.5-pro", 5000, 2500)
        expected = (5000 / 1_000_000 * 1.25) + (2500 / 1_000_000 * 5.00)
        assert abs(cost - expected) < 0.000001
        assert cost == 0.01875

    def test_zero_tokens(self):
        """Test cost calculation with zero tokens"""
        cost = compute_cost("openai", "gpt-4o", 0, 0)
        assert cost == 0.0

    def test_large_token_counts(self):
        """Test cost calculation with large token counts"""
        # 1M input, 500K output tokens
        cost = compute_cost("openai", "gpt-4o", 1_000_000, 500_000)
        expected = (1_000_000 / 1_000_000 * 2.50) + (500_000 / 1_000_000 * 10.00)
        assert abs(cost - expected) < 0.000001
        assert cost == 7.5

    def test_cost_rounding(self):
        """Test that costs are rounded to 6 decimal places"""
        cost = compute_cost("openai", "gpt-4o", 1, 1)
        # Should be rounded to 6 decimals
        assert len(str(cost).split(".")[-1]) <= 6


class TestConsistency:
    """Test consistency across different pricing methods"""

    def test_same_model_same_cost(self):
        """Test that same model with same tokens produces same cost"""
        cost1 = compute_cost("openai", "gpt-4o", 1000, 500)
        cost2 = compute_cost("openai", "gpt-4o", 1000, 500)
        assert cost1 == cost2

    def test_normalized_vs_raw_model_name(self):
        """Test that normalized and raw model names produce same cost"""
        cost1 = compute_cost("openai", "gpt-4o", 1000, 500)
        cost2 = compute_cost("openai", "gpt-4o-2024-05-13", 1000, 500)
        assert cost1 == cost2

    def test_case_insensitive_cost(self):
        """Test that cost calculation is case-insensitive"""
        cost1 = compute_cost("openai", "gpt-4o", 1000, 500)
        cost2 = compute_cost("OpenAI", "GPT-4O", 1000, 500)
        assert cost1 == cost2

