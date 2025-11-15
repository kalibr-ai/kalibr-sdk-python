"""
Kalibr SDK Instrumentation Module

Provides automatic instrumentation for LLM SDKs (OpenAI, Anthropic, Google)
using monkey-patching to emit OpenTelemetry-compatible spans.
"""

import os
from typing import List, Optional

from .registry import auto_instrument, get_instrumented_providers

__all__ = ["auto_instrument", "get_instrumented_providers"]
