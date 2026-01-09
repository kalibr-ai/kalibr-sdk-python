"""Vendor-agnostic cost adapters for LLM pricing.

Each adapter computes cost in USD based on:
- Model name
- Input tokens
- Output tokens
- Centralized pricing from kalibr.pricing

Supports:
- OpenAI (GPT-4, GPT-3.5, o1, etc.)
- Anthropic (Claude models)
- Google (Gemini models)
- Extensible for other vendors

Note: All pricing is now centralized in kalibr/pricing.py
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from .pricing import calculate_cost as _calculate_cost
from .pricing import get_pricing, get_supported_vendors


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
    """Cost adapter for OpenAI models.
    
    Uses centralized pricing from kalibr.pricing module.
    """

    def get_vendor_name(self) -> str:
        return "openai"

    def compute_cost(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Compute cost for OpenAI models using centralized pricing."""
        return _calculate_cost("openai", model_name, tokens_in, tokens_out)


class AnthropicCostAdapter(BaseCostAdapter):
    """Cost adapter for Anthropic Claude models.
    
    Uses centralized pricing from kalibr.pricing module.
    """

    def get_vendor_name(self) -> str:
        return "anthropic"

    def compute_cost(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Compute cost for Anthropic models using centralized pricing."""
        return _calculate_cost("anthropic", model_name, tokens_in, tokens_out)


class GoogleCostAdapter(BaseCostAdapter):
    """Cost adapter for Google Gemini models.
    
    Uses centralized pricing from kalibr.pricing module.
    """

    def get_vendor_name(self) -> str:
        return "google"

    def compute_cost(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Compute cost for Google models using centralized pricing."""
        return _calculate_cost("google", model_name, tokens_in, tokens_out)


class CostAdapterFactory:
    """Factory to get appropriate cost adapter for a vendor."""

    _adapters: Dict[str, BaseCostAdapter] = {
        "openai": OpenAICostAdapter(),
        "anthropic": AnthropicCostAdapter(),
        "google": GoogleCostAdapter(),
    }

    @classmethod
    def get_adapter(cls, vendor: str) -> Optional[BaseCostAdapter]:
        """Get cost adapter for vendor.

        Args:
            vendor: Vendor name (openai, anthropic, google, etc.)

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
        
        This is the recommended way to calculate costs - it uses
        centralized pricing from kalibr.pricing module.

        Args:
            vendor: Vendor name (openai, anthropic, google)
            model_name: Model identifier
            tokens_in: Input token count
            tokens_out: Output token count

        Returns:
            Cost in USD, rounded to 6 decimal places
        """
        # Use centralized pricing directly for better consistency
        return _calculate_cost(vendor, model_name, tokens_in, tokens_out)
