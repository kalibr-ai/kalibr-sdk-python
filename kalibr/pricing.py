"""Centralized pricing configuration for LLM providers.

This module is the single source of truth for all model pricing.
All cost adapters should import pricing from here to ensure consistency.

Pricing is in USD per 1 MILLION tokens (not per 1K).
This matches OpenAI's pricing page format and is easier to read.

To calculate cost:
    cost = (tokens / 1_000_000) * price_per_million

Last updated: January 2025
"""

from typing import Dict, Optional, Tuple

# Version tracking for pricing updates
PRICING_VERSION = "2025-01"

# =============================================================================
# OpenAI Pricing (per 1M tokens)
# Source: https://openai.com/pricing
# =============================================================================
OPENAI_PRICING: Dict[str, Dict[str, float]] = {
    # GPT-4 family
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-32k": {"input": 60.00, "output": 120.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
    # GPT-4o family
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-05-13": {"input": 5.00, "output": 15.00},
    # GPT-3.5 family
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-3.5-turbo-16k": {"input": 1.00, "output": 2.00},
    "gpt-3.5-turbo-instruct": {"input": 1.50, "output": 2.00},
    # o1 family (reasoning models)
    "o1": {"input": 15.00, "output": 60.00},
    "o1-preview": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 3.00, "output": 12.00},
    # Embeddings
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "text-embedding-ada-002": {"input": 0.10, "output": 0.0},
}

# =============================================================================
# Anthropic Pricing (per 1M tokens)
# Source: https://www.anthropic.com/pricing
# =============================================================================
ANTHROPIC_PRICING: Dict[str, Dict[str, float]] = {
    # Claude 3.5 family
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    # Claude 3 family
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    # Claude 2 family (legacy)
    "claude-2.1": {"input": 8.00, "output": 24.00},
    "claude-2.0": {"input": 8.00, "output": 24.00},
    "claude-instant-1.2": {"input": 0.80, "output": 2.40},
}

# =============================================================================
# Google Pricing (per 1M tokens)
# Source: https://ai.google.dev/pricing
# =============================================================================
GOOGLE_PRICING: Dict[str, Dict[str, float]] = {
    # Gemini 2.0 family
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash-exp": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash-thinking": {"input": 0.075, "output": 0.30},
    # Gemini 1.5 family
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-pro-latest": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-latest": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
    # Gemini 1.0 family (legacy)
    "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
    "gemini-pro": {"input": 0.50, "output": 1.50},
}

# =============================================================================
# Combined pricing lookup
# =============================================================================
ALL_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": OPENAI_PRICING,
    "anthropic": ANTHROPIC_PRICING,
    "google": GOOGLE_PRICING,
}

# Default pricing for unknown models (conservative estimate)
DEFAULT_PRICING: Dict[str, float] = {"input": 10.00, "output": 30.00}


def get_pricing(vendor: str, model: str) -> Dict[str, float]:
    """Get pricing for a specific vendor/model combination.
    
    Args:
        vendor: Provider name (openai, anthropic, google)
        model: Model identifier
        
    Returns:
        Dict with 'input' and 'output' prices per 1M tokens
    """
    vendor_lower = vendor.lower()
    model_lower = model.lower()
    
    # Get vendor pricing table
    vendor_pricing = ALL_PRICING.get(vendor_lower, {})
    
    # Try exact match first
    if model_lower in vendor_pricing:
        return vendor_pricing[model_lower]
    
    # Try fuzzy matching for model variants
    pricing = _fuzzy_match_model(vendor_lower, model_lower, vendor_pricing)
    if pricing:
        return pricing
    
    # Return default pricing for unknown models
    return DEFAULT_PRICING.copy()


def _fuzzy_match_model(
    vendor: str, 
    model: str, 
    vendor_pricing: Dict[str, Dict[str, float]]
) -> Optional[Dict[str, float]]:
    """Try to match model name with fuzzy logic.
    
    Handles cases like:
    - 'gpt-4o-2024-11-20' -> 'gpt-4o'
    - 'claude-3-5-sonnet-20241022' -> 'claude-3-5-sonnet'
    """
    # Remove date suffixes (e.g., -20240101, -2024-01-01)
    import re
    base_model = re.sub(r'-\d{4}[-]?\d{2}[-]?\d{2}$', '', model)
    if base_model in vendor_pricing:
        return vendor_pricing[base_model]
    
    # OpenAI-specific matching
    if vendor == "openai":
        if "gpt-4o-mini" in model:
            return vendor_pricing.get("gpt-4o-mini")
        elif "gpt-4o" in model:
            return vendor_pricing.get("gpt-4o")
        elif "gpt-4-turbo" in model:
            return vendor_pricing.get("gpt-4-turbo")
        elif "gpt-4" in model:
            return vendor_pricing.get("gpt-4")
        elif "gpt-3.5" in model:
            return vendor_pricing.get("gpt-3.5-turbo")
        elif "o1-mini" in model:
            return vendor_pricing.get("o1-mini")
        elif "o1" in model:
            return vendor_pricing.get("o1")
    
    # Anthropic-specific matching
    elif vendor == "anthropic":
        if "claude-3-5-sonnet" in model or "claude-3.5-sonnet" in model:
            return vendor_pricing.get("claude-3-5-sonnet")
        elif "claude-3-5-haiku" in model:
            return vendor_pricing.get("claude-3-5-haiku")
        elif "claude-3-opus" in model:
            return vendor_pricing.get("claude-3-opus")
        elif "claude-3-sonnet" in model:
            return vendor_pricing.get("claude-3-sonnet")
        elif "claude-3-haiku" in model:
            return vendor_pricing.get("claude-3-haiku")
        elif "claude-2" in model:
            return vendor_pricing.get("claude-2.1")
    
    # Google-specific matching  
    elif vendor == "google":
        if "gemini-2.0-flash" in model:
            return vendor_pricing.get("gemini-2.0-flash")
        elif "gemini-1.5-pro" in model:
            return vendor_pricing.get("gemini-1.5-pro")
        elif "gemini-1.5-flash-8b" in model:
            return vendor_pricing.get("gemini-1.5-flash-8b")
        elif "gemini-1.5-flash" in model:
            return vendor_pricing.get("gemini-1.5-flash")
        elif "gemini-pro" in model or "gemini-1.0" in model:
            return vendor_pricing.get("gemini-pro")
    
    return None


def calculate_cost(
    vendor: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate cost in USD for an LLM API call.
    
    Args:
        vendor: Provider name (openai, anthropic, google)
        model: Model identifier
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
        
    Returns:
        Total cost in USD, rounded to 6 decimal places
    """
    pricing = get_pricing(vendor, model)
    
    # Pricing is per 1M tokens
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    
    return round(input_cost + output_cost, 6)


def get_supported_vendors() -> list:
    """Get list of vendors with pricing data."""
    return list(ALL_PRICING.keys())


def get_supported_models(vendor: str) -> list:
    """Get list of models with pricing for a vendor."""
    return list(ALL_PRICING.get(vendor.lower(), {}).keys())

