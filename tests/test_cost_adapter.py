"""Tests for cost adapter implementations.

Tests OpenAICostAdapter, AnthropicCostAdapter, and CostAdapterFactory
to ensure they correctly use centralized pricing.
"""

import pytest
from kalibr.cost_adapter import (
    AnthropicCostAdapter,
    BaseCostAdapter,
    CostAdapterFactory,
    OpenAICostAdapter,
)


class TestOpenAICostAdapter:
    """Test OpenAI cost adapter"""

    def test_get_vendor_name(self):
        """Test that vendor name is correct"""
        adapter = OpenAICostAdapter()
        assert adapter.get_vendor_name() == "openai"

    def test_compute_cost_gpt4o(self):
        """Test cost computation for GPT-4o"""
        adapter = OpenAICostAdapter()
        cost = adapter.compute_cost("gpt-4o", 1000, 500)
        # GPT-4o: $2.50/1M input, $10.00/1M output
        expected = (1000 / 1_000_000 * 2.50) + (500 / 1_000_000 * 10.00)
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_gpt4(self):
        """Test cost computation for GPT-4"""
        adapter = OpenAICostAdapter()
        cost = adapter.compute_cost("gpt-4", 1000, 500)
        # GPT-4: $30.00/1M input, $60.00/1M output
        expected = (1000 / 1_000_000 * 30.00) + (500 / 1_000_000 * 60.00)
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_gpt4o_mini(self):
        """Test cost computation for GPT-4o-mini"""
        adapter = OpenAICostAdapter()
        cost = adapter.compute_cost("gpt-4o-mini", 1000, 500)
        # GPT-4o-mini: $0.15/1M input, $0.60/1M output
        expected = (1000 / 1_000_000 * 0.15) + (500 / 1_000_000 * 0.60)
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_with_date_suffix(self):
        """Test that models with date suffixes work correctly"""
        adapter = OpenAICostAdapter()
        cost1 = adapter.compute_cost("gpt-4o", 1000, 500)
        cost2 = adapter.compute_cost("gpt-4o-2024-05-13", 1000, 500)
        assert cost1 == cost2

    def test_compute_cost_unknown_model(self):
        """Test that unknown models fall back to default pricing"""
        adapter = OpenAICostAdapter()
        cost = adapter.compute_cost("unknown-model", 1000, 500)
        # Should fall back to GPT-4 pricing
        expected = (1000 / 1_000_000 * 30.00) + (500 / 1_000_000 * 60.00)
        assert abs(cost - expected) < 0.000001

    def test_zero_tokens(self):
        """Test cost with zero tokens"""
        adapter = OpenAICostAdapter()
        cost = adapter.compute_cost("gpt-4o", 0, 0)
        assert cost == 0.0


class TestAnthropicCostAdapter:
    """Test Anthropic cost adapter"""

    def test_get_vendor_name(self):
        """Test that vendor name is correct"""
        adapter = AnthropicCostAdapter()
        assert adapter.get_vendor_name() == "anthropic"

    def test_compute_cost_claude3_opus(self):
        """Test cost computation for Claude 3 Opus"""
        adapter = AnthropicCostAdapter()
        cost = adapter.compute_cost("claude-3-opus", 1000, 500)
        # Claude-3-opus: $15.00/1M input, $75.00/1M output
        expected = (1000 / 1_000_000 * 15.00) + (500 / 1_000_000 * 75.00)
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_claude3_sonnet(self):
        """Test cost computation for Claude 3 Sonnet"""
        adapter = AnthropicCostAdapter()
        cost = adapter.compute_cost("claude-3-sonnet", 1000, 500)
        # Claude-3-sonnet: $3.00/1M input, $15.00/1M output
        expected = (1000 / 1_000_000 * 3.00) + (500 / 1_000_000 * 15.00)
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_claude35_sonnet(self):
        """Test cost computation for Claude 3.5 Sonnet"""
        adapter = AnthropicCostAdapter()
        cost = adapter.compute_cost("claude-3-5-sonnet", 1000, 500)
        # Claude-3-5-sonnet: $3.00/1M input, $15.00/1M output
        expected = (1000 / 1_000_000 * 3.00) + (500 / 1_000_000 * 15.00)
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_claude3_haiku(self):
        """Test cost computation for Claude 3 Haiku"""
        adapter = AnthropicCostAdapter()
        cost = adapter.compute_cost("claude-3-haiku", 1000, 500)
        # Claude-3-haiku: $0.25/1M input, $1.25/1M output
        expected = (1000 / 1_000_000 * 0.25) + (500 / 1_000_000 * 1.25)
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_with_date_suffix(self):
        """Test that models with date suffixes work correctly"""
        adapter = AnthropicCostAdapter()
        cost1 = adapter.compute_cost("claude-3-5-sonnet", 1000, 500)
        cost2 = adapter.compute_cost("claude-3-5-sonnet-20240620", 1000, 500)
        assert cost1 == cost2

    def test_compute_cost_unknown_model(self):
        """Test that unknown models fall back to default pricing"""
        adapter = AnthropicCostAdapter()
        cost = adapter.compute_cost("unknown-model", 1000, 500)
        # Should fall back to Claude 3 Opus pricing
        expected = (1000 / 1_000_000 * 15.00) + (500 / 1_000_000 * 75.00)
        assert abs(cost - expected) < 0.000001


class TestCostAdapterFactory:
    """Test cost adapter factory"""

    def test_get_openai_adapter(self):
        """Test getting OpenAI adapter from factory"""
        adapter = CostAdapterFactory.get_adapter("openai")
        assert adapter is not None
        assert isinstance(adapter, OpenAICostAdapter)
        assert adapter.get_vendor_name() == "openai"

    def test_get_anthropic_adapter(self):
        """Test getting Anthropic adapter from factory"""
        adapter = CostAdapterFactory.get_adapter("anthropic")
        assert adapter is not None
        assert isinstance(adapter, AnthropicCostAdapter)
        assert adapter.get_vendor_name() == "anthropic"

    def test_get_adapter_case_insensitive(self):
        """Test that vendor name is case-insensitive"""
        adapter1 = CostAdapterFactory.get_adapter("OpenAI")
        adapter2 = CostAdapterFactory.get_adapter("openai")
        assert adapter1 is not None
        assert adapter2 is not None
        assert type(adapter1) == type(adapter2)

    def test_get_unknown_adapter(self):
        """Test getting adapter for unknown vendor"""
        adapter = CostAdapterFactory.get_adapter("unknown-vendor")
        assert adapter is None

    def test_compute_cost_via_factory(self):
        """Test computing cost via factory convenience method"""
        cost = CostAdapterFactory.compute_cost("openai", "gpt-4o", 1000, 500)
        expected = (1000 / 1_000_000 * 2.50) + (500 / 1_000_000 * 10.00)
        assert abs(cost - expected) < 0.000001

    def test_compute_cost_unknown_vendor(self):
        """Test that unknown vendor returns 0.0"""
        cost = CostAdapterFactory.compute_cost("unknown-vendor", "some-model", 1000, 500)
        assert cost == 0.0

    def test_register_custom_adapter(self):
        """Test registering a custom adapter"""

        class CustomAdapter(BaseCostAdapter):
            def get_vendor_name(self):
                return "custom"

            def compute_cost(self, model_name, tokens_in, tokens_out):
                return 1.0  # Fixed cost for testing

        custom_adapter = CustomAdapter()
        CostAdapterFactory.register_adapter("custom", custom_adapter)

        # Test that we can retrieve it
        adapter = CostAdapterFactory.get_adapter("custom")
        assert adapter is not None
        assert adapter.get_vendor_name() == "custom"

        # Test that we can use it
        cost = CostAdapterFactory.compute_cost("custom", "test-model", 1000, 500)
        assert cost == 1.0


class TestConsistencyAcrossAdapters:
    """Test consistency between adapters and centralized pricing"""

    def test_openai_adapter_matches_pricing_module(self):
        """Test that OpenAI adapter matches pricing module"""
        from kalibr.pricing import compute_cost as pricing_compute_cost

        adapter = OpenAICostAdapter()
        adapter_cost = adapter.compute_cost("gpt-4o", 1000, 500)
        pricing_cost = pricing_compute_cost("openai", "gpt-4o", 1000, 500)
        assert adapter_cost == pricing_cost

    def test_anthropic_adapter_matches_pricing_module(self):
        """Test that Anthropic adapter matches pricing module"""
        from kalibr.pricing import compute_cost as pricing_compute_cost

        adapter = AnthropicCostAdapter()
        adapter_cost = adapter.compute_cost("claude-3-opus", 1000, 500)
        pricing_cost = pricing_compute_cost("anthropic", "claude-3-opus", 1000, 500)
        assert adapter_cost == pricing_cost

    def test_factory_matches_pricing_module(self):
        """Test that factory matches pricing module"""
        from kalibr.pricing import compute_cost as pricing_compute_cost

        factory_cost = CostAdapterFactory.compute_cost("openai", "gpt-4o", 1000, 500)
        pricing_cost = pricing_compute_cost("openai", "gpt-4o", 1000, 500)
        assert factory_cost == pricing_cost

