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

Note: All adapters now use centralized pricing from kalibr.pricing module.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Optional

from kalibr.pricing import get_pricing, get_voice_pricing, normalize_model_name


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
        """Compute cost for OpenAI models.
        
        Args:
            model_name: Model identifier (e.g., "gpt-4o", "gpt-4")
            tokens_in: Input token count
            tokens_out: Output token count
            
        Returns:
            Cost in USD (rounded to 6 decimal places)
        """
        # Get pricing from centralized module
        pricing, _ = get_pricing("openai", model_name)

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (tokens_in / 1_000_000) * pricing["input"]
        output_cost = (tokens_out / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)


class AnthropicCostAdapter(BaseCostAdapter):
    """Cost adapter for Anthropic Claude models.
    
    Uses centralized pricing from kalibr.pricing module.
    """

    def get_vendor_name(self) -> str:
        return "anthropic"

    def compute_cost(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Compute cost for Anthropic models.
        
        Args:
            model_name: Model identifier (e.g., "claude-3-opus", "claude-3-5-sonnet")
            tokens_in: Input token count
            tokens_out: Output token count
            
        Returns:
            Cost in USD (rounded to 6 decimal places)
        """
        # Get pricing from centralized module
        pricing, _ = get_pricing("anthropic", model_name)

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (tokens_in / 1_000_000) * pricing["input"]
        output_cost = (tokens_out / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)


class BaseVoiceCostAdapter(ABC):
    """Base class for voice vendor cost adapters."""

    @abstractmethod
    def compute_cost(
        self, model_name: str, characters: int = 0, audio_duration_minutes: float = 0.0
    ) -> float:
        """Compute cost in USD for a voice API call.

        Args:
            model_name: Model identifier
            characters: Number of characters (for TTS)
            audio_duration_minutes: Audio duration in minutes (for STT)

        Returns:
            Cost in USD
        """
        pass

    @abstractmethod
    def get_vendor_name(self) -> str:
        """Return vendor name."""
        pass


class ElevenLabsCostAdapter(BaseVoiceCostAdapter):
    """Cost adapter for ElevenLabs voice models."""

    def get_vendor_name(self) -> str:
        return "elevenlabs"

    def compute_cost(
        self, model_name: str, characters: int = 0, audio_duration_minutes: float = 0.0
    ) -> float:
        pricing, _ = get_voice_pricing("elevenlabs", model_name)
        cost = (characters / 1_000) * pricing["price"]
        return round(cost, 6)


class OpenAIVoiceCostAdapter(BaseVoiceCostAdapter):
    """Cost adapter for OpenAI voice models (TTS and Whisper)."""

    def get_vendor_name(self) -> str:
        return "openai"

    def compute_cost(
        self, model_name: str, characters: int = 0, audio_duration_minutes: float = 0.0
    ) -> float:
        pricing, _ = get_voice_pricing("openai", model_name)
        if pricing["unit"] == "per_1k_chars":
            cost = (characters / 1_000) * pricing["price"]
        elif pricing["unit"] == "per_minute":
            cost = audio_duration_minutes * pricing["price"]
        else:
            cost = 0.0
        return round(cost, 6)


class DeepgramCostAdapter(BaseVoiceCostAdapter):
    """Cost adapter for Deepgram voice models."""

    def get_vendor_name(self) -> str:
        return "deepgram"

    def compute_cost(
        self, model_name: str, characters: int = 0, audio_duration_minutes: float = 0.0
    ) -> float:
        pricing, _ = get_voice_pricing("deepgram", model_name)
        if pricing["unit"] == "per_1k_chars":
            cost = (characters / 1_000) * pricing["price"]
        elif pricing["unit"] == "per_minute":
            cost = audio_duration_minutes * pricing["price"]
        else:
            cost = 0.0
        return round(cost, 6)


class CostAdapterFactory:
    """Factory to get appropriate cost adapter for a vendor."""

    _adapters: Dict[str, BaseCostAdapter] = {
        "openai": OpenAICostAdapter(),
        "anthropic": AnthropicCostAdapter(),
    }

    _voice_adapters: Dict[str, BaseVoiceCostAdapter] = {
        "elevenlabs": ElevenLabsCostAdapter(),
        "openai": OpenAIVoiceCostAdapter(),
        "deepgram": DeepgramCostAdapter(),
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

    @classmethod
    def get_voice_adapter(cls, vendor: str) -> Optional[BaseVoiceCostAdapter]:
        """Get voice cost adapter for vendor."""
        return cls._voice_adapters.get(vendor.lower())

    @classmethod
    def register_voice_adapter(cls, vendor: str, adapter: BaseVoiceCostAdapter):
        """Register a custom voice cost adapter."""
        cls._voice_adapters[vendor.lower()] = adapter

    @classmethod
    def compute_voice_cost(
        cls,
        vendor: str,
        model_name: str,
        characters: int = 0,
        audio_duration_minutes: float = 0.0,
    ) -> float:
        """Convenience method to compute voice cost.

        Returns:
            Cost in USD, or 0.0 if vendor not supported
        """
        adapter = cls.get_voice_adapter(vendor)
        if adapter:
            return adapter.compute_cost(model_name, characters, audio_duration_minutes)
        return 0.0
