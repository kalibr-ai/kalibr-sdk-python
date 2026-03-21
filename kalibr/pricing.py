"""Centralized pricing data for all LLM vendors.

This module serves as the single source of truth for model pricing across
the entire Kalibr SDK. All cost adapters and instrumentation modules should
use this pricing data to ensure consistency.

All prices are in USD per 1 million tokens, matching the format used by
major LLM providers (OpenAI, Anthropic, etc.) on their pricing pages.

Version: 2026-01
Last Updated: January 2026
"""

from typing import Any, Dict, Optional, Tuple, Union

# Pricing version for tracking updates
PRICING_VERSION = "2026-01"

# All prices in USD per 1M tokens
MODEL_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        # GPT-5 models (future-proofing)
        "gpt-5": {"input": 5.00, "output": 15.00},
        "gpt-5-turbo": {"input": 2.50, "output": 7.50},
        # GPT-4 models
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        # GPT-3.5 models
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "gpt-3.5-turbo-16k": {"input": 1.00, "output": 2.00},
    },
    "anthropic": {
        # Claude 4 models (future-proofing)
        "claude-4-opus": {"input": 15.00, "output": 75.00},
        "claude-4-sonnet": {"input": 3.00, "output": 15.00},
        # Claude 3.5/3.7 models (Sonnet 4 is actually Claude 3.7)
        "claude-sonnet-4": {"input": 3.00, "output": 15.00},
        "claude-3-7-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        # Claude 3 models
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        # Claude 2 models
        "claude-2.1": {"input": 8.00, "output": 24.00},
        "claude-2.0": {"input": 8.00, "output": 24.00},
        "claude-instant-1.2": {"input": 0.80, "output": 2.40},
    },
    "google": {
        # Gemini 2.5 models
        "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
        # Gemini 2.0 models
        "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
        "gemini-2.0-flash-thinking": {"input": 0.075, "output": 0.30},
        # Gemini 1.5 models
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
        # Gemini 1.0 models
        "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
        "gemini-pro": {"input": 0.50, "output": 1.50},  # Alias
    },
}

# Default fallback pricing per vendor (highest tier pricing for safety)
DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    "openai": {"input": 30.00, "output": 60.00},  # GPT-4 pricing
    "anthropic": {"input": 15.00, "output": 75.00},  # Claude 3 Opus pricing
    "google": {"input": 1.25, "output": 5.00},  # Gemini 1.5 Pro pricing
}


def normalize_model_name(vendor: str, model_name: str) -> str:
    """Normalize model name to match pricing table keys.

    Handles version suffixes, date stamps, and common variations.

    Args:
        vendor: Vendor name (openai, anthropic, google)
        model_name: Raw model name from API

    Returns:
        Normalized model name that matches pricing table, or original if no match

    Example:
        >>> normalize_model_name("openai", "gpt-4o-2024-05-13")
        'gpt-4o'
        >>> normalize_model_name("anthropic", "claude-3-5-sonnet-20240620")
        'claude-3-5-sonnet'
    """
    vendor = vendor.lower()
    model_lower = model_name.lower()

    # Get vendor pricing table
    vendor_models = MODEL_PRICING.get(vendor, {})

    # Direct match
    if model_lower in vendor_models:
        return model_lower

    # OpenAI fuzzy matching
    if vendor == "openai":
        # Remove date suffixes like -20240513
        base_model = model_lower.split("-2")[0] if "-2" in model_lower else model_lower

        # Try direct match on base
        if base_model in vendor_models:
            return base_model

        # Fuzzy match in priority order
        if "gpt-4o-mini" in model_lower:
            return "gpt-4o-mini"
        elif "gpt-4o" in model_lower:
            return "gpt-4o"
        elif "gpt-5-turbo" in model_lower:
            return "gpt-5-turbo"
        elif "gpt-5" in model_lower:
            return "gpt-5"
        elif "gpt-4-turbo" in model_lower:
            return "gpt-4-turbo"
        elif "gpt-4" in model_lower:
            return "gpt-4"
        elif "gpt-3.5-turbo-16k" in model_lower:
            return "gpt-3.5-turbo-16k"
        elif "gpt-3.5" in model_lower:
            return "gpt-3.5-turbo"

    # Anthropic fuzzy matching
    elif vendor == "anthropic":
        # Try fuzzy matching for versioned models
        if "claude-3.5-sonnet" in model_lower or "claude-3-5-sonnet" in model_lower:
            return "claude-3-5-sonnet"
        elif "claude-sonnet-4" in model_lower or "sonnet-4" in model_lower:
            return "claude-sonnet-4"
        elif "claude-3-7-sonnet" in model_lower:
            return "claude-3-7-sonnet"
        elif "claude-4-opus" in model_lower:
            return "claude-4-opus"
        elif "claude-4-sonnet" in model_lower:
            return "claude-4-sonnet"
        elif "claude-3-opus" in model_lower:
            return "claude-3-opus"
        elif "claude-3-sonnet" in model_lower:
            return "claude-3-sonnet"
        elif "claude-3-haiku" in model_lower:
            return "claude-3-haiku"
        elif "claude-2.1" in model_lower:
            return "claude-2.1"
        elif "claude-2.0" in model_lower or "claude-2" in model_lower:
            return "claude-2.0"
        elif "claude-instant" in model_lower:
            return "claude-instant-1.2"

    # Google fuzzy matching
    elif vendor == "google":
        # Try fuzzy matching for versioned models
        if "gemini-2.5-pro" in model_lower:
            return "gemini-2.5-pro"
        elif "gemini-2.5-flash" in model_lower:
            return "gemini-2.5-flash"
        elif "gemini-2.0-flash-thinking" in model_lower:
            return "gemini-2.0-flash-thinking"
        elif "gemini-2.0-flash" in model_lower:
            return "gemini-2.0-flash"
        elif "gemini-1.5-flash-8b" in model_lower:
            return "gemini-1.5-flash-8b"
        elif "gemini-1.5-flash" in model_lower:
            return "gemini-1.5-flash"
        elif "gemini-1.5-pro" in model_lower:
            return "gemini-1.5-pro"
        elif "gemini-1.0-pro" in model_lower or "gemini-pro" in model_lower:
            return "gemini-pro"

    # Return original if no match found
    return model_lower


def get_pricing(
    vendor: str, model_name: str
) -> Tuple[Dict[str, float], str]:
    """Get pricing for a specific vendor and model.

    Args:
        vendor: Vendor name (openai, anthropic, google)
        model_name: Model identifier

    Returns:
        Tuple of (pricing dict with 'input' and 'output' keys in USD per 1M tokens,
                  normalized model name used)

    Example:
        >>> pricing, normalized = get_pricing("openai", "gpt-4o")
        >>> print(pricing)
        {'input': 2.50, 'output': 10.00}
        >>> print(normalized)
        'gpt-4o'
    """
    vendor = vendor.lower()
    normalized_model = normalize_model_name(vendor, model_name)

    # Get vendor pricing table
    vendor_models = MODEL_PRICING.get(vendor, {})

    # Try to get pricing for normalized model
    pricing = vendor_models.get(normalized_model)

    # Fall back to default vendor pricing if not found
    if pricing is None:
        pricing = DEFAULT_PRICING.get(vendor, {"input": 20.00, "output": 60.00})

    return pricing, normalized_model


def compute_cost(
    vendor: str, model_name: str, input_tokens: int, output_tokens: int
) -> float:
    """Compute cost in USD for given vendor, model, and token counts.

    This is a convenience function that combines pricing lookup and cost calculation.

    Args:
        vendor: Vendor name (openai, anthropic, google)
        model_name: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD (rounded to 6 decimal places)

    Example:
        >>> cost = compute_cost("openai", "gpt-4o", 1000, 500)
        >>> print(f"${cost:.6f}")
        $0.007500
    """
    pricing, _ = get_pricing(vendor, model_name)

    # Calculate cost (pricing is per 1M tokens)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return round(input_cost + output_cost, 6)


# ============================================================================
# UNIT PRICING — Flexible pricing for any billing unit
# ============================================================================
# All prices are per single unit (one character, one second, one image, etc.)
# Structured as nested dicts: vendor → model → {"unit": ..., "price_per_unit": ...}
UNIT_PRICING: Dict[str, Dict[str, Dict[str, Any]]] = {
    "elevenlabs": {
        # TTS (per character)
        "eleven_multilingual_v2": {"unit": "characters", "price_per_unit": 0.0003},
        "eleven_multilingual_v1": {"unit": "characters", "price_per_unit": 0.0003},
        "eleven_monolingual_v1": {"unit": "characters", "price_per_unit": 0.0003},
        "eleven_turbo_v2": {"unit": "characters", "price_per_unit": 0.00015},
        "eleven_turbo_v2_5": {"unit": "characters", "price_per_unit": 0.00015},
        "eleven_flash_v2": {"unit": "characters", "price_per_unit": 0.00008},
        "eleven_flash_v2_5": {"unit": "characters", "price_per_unit": 0.00008},
    },
    "openai": {
        # TTS (per character)
        "tts-1": {"unit": "characters", "price_per_unit": 0.000015},
        "tts-1-hd": {"unit": "characters", "price_per_unit": 0.00003},
        # STT (per second)
        "whisper-1": {"unit": "audio_seconds", "price_per_unit": 0.0001},
    },
    "deepgram": {
        # STT (per second)
        "nova-2": {"unit": "audio_seconds", "price_per_unit": 0.0000717},
        "nova-2-general": {"unit": "audio_seconds", "price_per_unit": 0.0000717},
        "nova-2-meeting": {"unit": "audio_seconds", "price_per_unit": 0.0000717},
        "nova-2-phonecall": {"unit": "audio_seconds", "price_per_unit": 0.0000717},
        "nova": {"unit": "audio_seconds", "price_per_unit": 0.0000717},
        "enhanced": {"unit": "audio_seconds", "price_per_unit": 0.0002417},
        "base": {"unit": "audio_seconds", "price_per_unit": 0.0002083},
        # TTS — Aura voices (per character)
        "aura-asteria-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-luna-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-stella-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-athena-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-hera-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-orion-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-arcas-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-perseus-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-angus-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-orpheus-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-helios-en": {"unit": "characters", "price_per_unit": 0.0000065},
        "aura-zeus-en": {"unit": "characters", "price_per_unit": 0.0000065},
    },
}


def compute_cost_flexible(
    vendor: str, model: str, usage_metrics: Dict[str, Any]
) -> float:
    """Compute cost for any billing unit type.

    Args:
        vendor: Vendor name (e.g., "elevenlabs", "openai", "deepgram")
        model: Model identifier
        usage_metrics: Dict mapping unit type to quantity,
                       e.g. {"characters": 3000} or {"audio_seconds": 120}

    Returns:
        Cost in USD (rounded to 6 decimal places)
    """
    vendor = vendor.lower()
    model = model.lower()

    pricing = UNIT_PRICING.get(vendor, {}).get(model)
    if pricing is None:
        return 0.0

    unit = pricing["unit"]
    price_per_unit = pricing["price_per_unit"]

    quantity = usage_metrics.get(unit, 0)
    return round(price_per_unit * quantity, 6)

