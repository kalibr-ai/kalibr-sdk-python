"""Centralized pricing data for all LLM vendors.

This module serves as the single source of truth for model pricing across
the entire Kalibr SDK. All cost adapters and instrumentation modules should
use this pricing data to ensure consistency.

All prices are in USD per 1 million tokens, matching the format used by
major LLM providers (OpenAI, Anthropic, etc.) on their pricing pages.

Version: 2026-01
Last Updated: January 2026
"""

from typing import Dict, Optional, Tuple, Union

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
# VOICE MODEL PRICING
# ============================================================================
# Prices vary by unit: per_1k_chars for TTS, per_minute for STT
VOICE_PRICING: Dict[str, Dict[str, Dict[str, Union[str, float]]]] = {
    "elevenlabs": {
        "eleven_multilingual_v2": {"unit": "per_1k_chars", "price": 0.30},
        "eleven_multilingual_v1": {"unit": "per_1k_chars", "price": 0.30},
        "eleven_monolingual_v1": {"unit": "per_1k_chars", "price": 0.30},
        "eleven_turbo_v2": {"unit": "per_1k_chars", "price": 0.15},
        "eleven_turbo_v2_5": {"unit": "per_1k_chars", "price": 0.15},
        "eleven_flash_v2": {"unit": "per_1k_chars", "price": 0.08},
        "eleven_flash_v2_5": {"unit": "per_1k_chars", "price": 0.08},
    },
    "openai": {
        "tts-1": {"unit": "per_1k_chars", "price": 0.015},
        "tts-1-hd": {"unit": "per_1k_chars", "price": 0.030},
        "whisper-1": {"unit": "per_minute", "price": 0.006},
    },
    "deepgram": {
        "nova-2": {"unit": "per_minute", "price": 0.0043},
        "nova-2-general": {"unit": "per_minute", "price": 0.0043},
        "nova-2-meeting": {"unit": "per_minute", "price": 0.0043},
        "nova-2-phonecall": {"unit": "per_minute", "price": 0.0043},
        "nova": {"unit": "per_minute", "price": 0.0043},
        "enhanced": {"unit": "per_minute", "price": 0.0145},
        "base": {"unit": "per_minute", "price": 0.0125},
        "aura-asteria-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-luna-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-stella-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-athena-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-hera-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-orion-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-arcas-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-perseus-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-angus-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-orpheus-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-helios-en": {"unit": "per_1k_chars", "price": 0.0065},
        "aura-zeus-en": {"unit": "per_1k_chars", "price": 0.0065},
    },
}

VOICE_DEFAULT_PRICING: Dict[str, Dict[str, Union[str, float]]] = {
    "elevenlabs": {"unit": "per_1k_chars", "price": 0.30},
    "openai": {"unit": "per_1k_chars", "price": 0.030},
    "deepgram": {"unit": "per_minute", "price": 0.0043},
}


def normalize_voice_model_name(vendor: str, model_name: str) -> str:
    """Normalize voice model name to match pricing table keys.

    Args:
        vendor: Vendor name (elevenlabs, openai, deepgram)
        model_name: Raw model name

    Returns:
        Normalized model name
    """
    vendor = vendor.lower()
    model_lower = model_name.lower()

    vendor_models = VOICE_PRICING.get(vendor, {})
    if model_lower in vendor_models:
        return model_lower

    if vendor == "deepgram":
        # nova-2-general variants -> nova-2-general, etc.
        for key in vendor_models:
            if key in model_lower:
                return key
        if "nova-2" in model_lower:
            return "nova-2"
        if "nova" in model_lower:
            return "nova"
        if "aura" in model_lower:
            return "aura-asteria-en"

    elif vendor == "elevenlabs":
        for key in vendor_models:
            if key in model_lower:
                return key
        if "flash" in model_lower:
            return "eleven_flash_v2_5"
        if "turbo" in model_lower:
            return "eleven_turbo_v2_5"
        if "multilingual" in model_lower:
            return "eleven_multilingual_v2"

    elif vendor == "openai":
        if "tts-1-hd" in model_lower:
            return "tts-1-hd"
        if "tts" in model_lower:
            return "tts-1"
        if "whisper" in model_lower:
            return "whisper-1"

    return model_lower


def get_voice_pricing(
    vendor: str, model_name: str
) -> Tuple[Dict[str, Union[str, float]], str]:
    """Get pricing for a voice model.

    Args:
        vendor: Vendor name (elevenlabs, openai, deepgram)
        model_name: Model identifier

    Returns:
        Tuple of (pricing dict with 'unit' and 'price' keys, normalized model name)
    """
    vendor = vendor.lower()
    normalized = normalize_voice_model_name(vendor, model_name)

    vendor_models = VOICE_PRICING.get(vendor, {})
    pricing = vendor_models.get(normalized)

    if pricing is None:
        pricing = VOICE_DEFAULT_PRICING.get(vendor, {"unit": "per_1k_chars", "price": 0.30})

    return pricing, normalized


def compute_voice_cost(
    vendor: str,
    model_name: str,
    characters: int = 0,
    audio_duration_minutes: float = 0.0,
) -> float:
    """Compute cost in USD for a voice API call.

    Args:
        vendor: Vendor name (elevenlabs, openai, deepgram)
        model_name: Model identifier
        characters: Number of characters (for TTS)
        audio_duration_minutes: Audio duration in minutes (for STT)

    Returns:
        Cost in USD (rounded to 6 decimal places)
    """
    pricing, _ = get_voice_pricing(vendor, model_name)

    unit = pricing["unit"]
    price = pricing["price"]

    if unit == "per_1k_chars":
        cost = (characters / 1_000) * price
    elif unit == "per_minute":
        cost = audio_duration_minutes * price
    else:
        cost = 0.0

    return round(cost, 6)

