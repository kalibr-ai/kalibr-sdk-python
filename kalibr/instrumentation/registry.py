"""
Instrumentation Registry

Handles auto-discovery and registration of LLM SDK instrumentations.
Provides a central place to manage which SDKs are instrumented.
"""

import os
from typing import Dict, List, Set

# Track which providers have been instrumented
_instrumented_providers: Set[str] = set()


def auto_instrument(providers: List[str] = None) -> Dict[str, bool]:
    """
    Auto-discover and instrument LLM SDKs

    Args:
        providers: List of provider names to instrument.
                   If None, attempts to instrument all supported providers.
                   Supported: ["openai", "anthropic", "google"]

    Returns:
        Dictionary mapping provider names to instrumentation success status
    """
    global _instrumented_providers

    # Default to all providers if none specified
    if providers is None:
        providers = ["openai", "anthropic", "google"]

    results = {}

    for provider in providers:
        provider_lower = provider.lower()

        # Skip if already instrumented
        if provider_lower in _instrumented_providers:
            results[provider_lower] = True
            continue

        try:
            if provider_lower == "openai":
                from . import openai_instr

                success = openai_instr.instrument()
                results[provider_lower] = success
                if success:
                    _instrumented_providers.add(provider_lower)
                    print(f"✅ Instrumented OpenAI SDK")

            elif provider_lower == "anthropic":
                from . import anthropic_instr

                success = anthropic_instr.instrument()
                results[provider_lower] = success
                if success:
                    _instrumented_providers.add(provider_lower)
                    print(f"✅ Instrumented Anthropic SDK")

            elif provider_lower == "google":
                from . import google_instr

                success = google_instr.instrument()
                results[provider_lower] = success
                if success:
                    _instrumented_providers.add(provider_lower)
                    print(f"✅ Instrumented Google Generative AI SDK")

            else:
                print(f"⚠️  Unknown provider: {provider}")
                results[provider_lower] = False

        except ImportError as e:
            print(f"⚠️  {provider} SDK not installed, skipping instrumentation")
            results[provider_lower] = False
        except Exception as e:
            print(f"❌ Failed to instrument {provider}: {e}")
            results[provider_lower] = False

    return results


def uninstrument_all() -> Dict[str, bool]:
    """
    Remove instrumentation from all previously instrumented SDKs

    Returns:
        Dictionary mapping provider names to uninstrumentation success status
    """
    global _instrumented_providers

    results = {}
    providers_to_uninstrument = list(_instrumented_providers)

    for provider in providers_to_uninstrument:
        try:
            if provider == "openai":
                from . import openai_instr

                success = openai_instr.uninstrument()
                results[provider] = success
                if success:
                    _instrumented_providers.discard(provider)
                    print(f"✅ Uninstrumented OpenAI SDK")

            elif provider == "anthropic":
                from . import anthropic_instr

                success = anthropic_instr.uninstrument()
                results[provider] = success
                if success:
                    _instrumented_providers.discard(provider)
                    print(f"✅ Uninstrumented Anthropic SDK")

            elif provider == "google":
                from . import google_instr

                success = google_instr.uninstrument()
                results[provider] = success
                if success:
                    _instrumented_providers.discard(provider)
                    print(f"✅ Uninstrumented Google Generative AI SDK")

        except Exception as e:
            print(f"❌ Failed to uninstrument {provider}: {e}")
            results[provider] = False

    return results


def get_instrumented_providers() -> List[str]:
    """
    Get list of currently instrumented providers

    Returns:
        List of provider names that are currently instrumented
    """
    return list(_instrumented_providers)


def is_instrumented(provider: str) -> bool:
    """
    Check if a specific provider is instrumented

    Args:
        provider: Provider name to check

    Returns:
        True if provider is instrumented, False otherwise
    """
    return provider.lower() in _instrumented_providers
