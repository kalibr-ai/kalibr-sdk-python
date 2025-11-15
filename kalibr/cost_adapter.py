"""Vendor-agnostic cost adapters for LLM pricing.

Each adapter computes cost in USD based on:
- Model name
- Input tokens
- Output tokens
- Pricing table (versioned)

Supports:
- OpenAI (GPT-4, GPT-3.5, etc.)
- Anthropic (Claude models)
- Extensible for other vendors
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseCostAdapter(ABC):
    """Base class for vendor cost adapters."""

    @abstractmethod
    def compute_cost(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Compute cost in USD for given model and token counts.

        Args:
            model_name: Model identifier
            tokens_in: Input token count
            tokens_out: Output token count

        Returns:
            Cost in USD (e.g., 0.0123)
        """
        pass

    @abstractmethod
    def get_vendor_name(self) -> str:
        """Return vendor name (e.g., 'openai', 'anthropic')."""
        pass


class OpenAICostAdapter(BaseCostAdapter):
    """Cost adapter for OpenAI models."""

    # OpenAI pricing as of 2025 (per 1M tokens)
    # Source: https://openai.com/pricing
    PRICING = {
        "gpt-4": {
            "input": 30.00,  # $30/1M input tokens
            "output": 60.00,  # $60/1M output tokens
        },
        "gpt-4-turbo": {
            "input": 10.00,
            "output": 30.00,
        },
        "gpt-4o": {
            "input": 2.50,
            "output": 10.00,
        },
        "gpt-3.5-turbo": {
            "input": 0.50,
            "output": 1.50,
        },
        "gpt-4o-mini": {
            "input": 0.15,
            "output": 0.60,
        },
    }

    def get_vendor_name(self) -> str:
        return "openai"

    def compute_cost(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Compute cost for OpenAI models."""
        # Normalize model name
        model_key = self._normalize_model_name(model_name)

        # Get pricing (default to gpt-4 if unknown)
        pricing = self.PRICING.get(model_key, self.PRICING["gpt-4"])

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (tokens_in / 1_000_000) * pricing["input"]
        output_cost = (tokens_out / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)

    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name to match pricing table."""
        model_lower = model_name.lower()

        # Direct matches
        if model_lower in self.PRICING:
            return model_lower

        # Fuzzy matches
        if "gpt-4o-mini" in model_lower:
            return "gpt-4o-mini"
        elif "gpt-4o" in model_lower:
            return "gpt-4o"
        elif "gpt-4-turbo" in model_lower:
            return "gpt-4-turbo"
        elif "gpt-4" in model_lower:
            return "gpt-4"
        elif "gpt-3.5" in model_lower:
            return "gpt-3.5-turbo"

        # Default to gpt-4 for unknown models
        return "gpt-4"


class AnthropicCostAdapter(BaseCostAdapter):
    """Cost adapter for Anthropic Claude models."""

    # Anthropic pricing as of 2025 (per 1M tokens)
    # Source: https://www.anthropic.com/pricing
    PRICING = {
        "claude-3-opus": {
            "input": 15.00,
            "output": 75.00,
        },
        "claude-3-sonnet": {
            "input": 3.00,
            "output": 15.00,
        },
        "claude-3-haiku": {
            "input": 0.25,
            "output": 1.25,
        },
        "claude-3.5-sonnet": {
            "input": 3.00,
            "output": 15.00,
        },
    }

    def get_vendor_name(self) -> str:
        return "anthropic"

    def compute_cost(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Compute cost for Anthropic models."""
        # Normalize model name
        model_key = self._normalize_model_name(model_name)

        # Get pricing (default to opus if unknown)
        pricing = self.PRICING.get(model_key, self.PRICING["claude-3-opus"])

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (tokens_in / 1_000_000) * pricing["input"]
        output_cost = (tokens_out / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)

    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name to match pricing table."""
        model_lower = model_name.lower()

        # Direct matches
        if model_lower in self.PRICING:
            return model_lower

        # Fuzzy matches
        if "claude-3.5-sonnet" in model_lower or "claude-3-5-sonnet" in model_lower:
            return "claude-3.5-sonnet"
        elif "claude-3-opus" in model_lower:
            return "claude-3-opus"
        elif "claude-3-sonnet" in model_lower:
            return "claude-3-sonnet"
        elif "claude-3-haiku" in model_lower:
            return "claude-3-haiku"

        # Default to opus for unknown models
        return "claude-3-opus"


class CostAdapterFactory:
    """Factory to get appropriate cost adapter for a vendor."""

    _adapters: Dict[str, BaseCostAdapter] = {
        "openai": OpenAICostAdapter(),
        "anthropic": AnthropicCostAdapter(),
    }

    @classmethod
    def get_adapter(cls, vendor: str) -> Optional[BaseCostAdapter]:
        """Get cost adapter for vendor.

        Args:
            vendor: Vendor name (openai, anthropic, etc.)

        Returns:
            Cost adapter instance or None if not supported
        """
        return cls._adapters.get(vendor.lower())

    @classmethod
    def register_adapter(cls, vendor: str, adapter: BaseCostAdapter):
        """Register a custom cost adapter.

        Args:
            vendor: Vendor name
            adapter: Cost adapter instance
        """
        cls._adapters[vendor.lower()] = adapter

    @classmethod
    def compute_cost(cls, vendor: str, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Convenience method to compute cost.

        Args:
            vendor: Vendor name
            model_name: Model identifier
            tokens_in: Input token count
            tokens_out: Output token count

        Returns:
            Cost in USD, or 0.0 if vendor not supported
        """
        adapter = cls.get_adapter(vendor)
        if adapter:
            return adapter.compute_cost(model_name, tokens_in, tokens_out)
        return 0.0
