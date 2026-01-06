"""Kalibr SDK v1.2.0 - LLM Observability & Tracing Framework

Features:
- **Auto-Instrumentation**: Zero-config tracing of OpenAI, Anthropic, Google SDK calls
- **OpenTelemetry**: OTel-compatible spans with OTLP export
- **Tracing**: Complete telemetry with @trace decorator
- **Cost Tracking**: Multi-vendor cost calculation (OpenAI, Anthropic, etc.)
- **Error Handling**: Automatic error capture with stack traces
- **Analytics**: ClickHouse-backed analytics and alerting

Usage - Auto-Instrumentation:
    from kalibr import auto_instrument
    import openai  # Automatically instrumented!

    auto_instrument(["openai", "anthropic", "google"])

    # All LLM calls are now traced automatically
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )

Usage - Manual Tracing:
    from kalibr import trace

    @trace(operation="chat_completion", vendor="openai", model="gpt-4")
    def call_openai(prompt):
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response

CLI Usage:
    kalibr run my_app.py                # Run with auto-tracing
    kalibr version                       # Show version
"""

__version__ = "1.2.0"

# Auto-instrument LLM SDKs on import (can be disabled via env var)
import os

# ============================================================================
# OBSERVABILITY & TRACING (from 1023)
# ============================================================================
from .client import KalibrClient

# ============================================================================
# PHASE 1: SDK INSTRUMENTATION & OPENTELEMETRY (v1.1.0)
# ============================================================================
from .collector import (
    get_tracer_provider,
)
from .collector import is_configured as is_collector_configured
from .collector import (
    setup_collector,
)
from .context import (
    get_parent_span_id,
    get_trace_id,
    new_trace_id,
    trace_context,
    # Goal context (v1.3.0)
    goal,
    set_goal,
    get_goal,
    clear_goal,
)
from .cost_adapter import (
    AnthropicCostAdapter,
    BaseCostAdapter,
    CostAdapterFactory,
    OpenAICostAdapter,
)
from .instrumentation import auto_instrument, get_instrumented_providers

from .models import EventData, TraceConfig
from .simple_tracer import trace
from .trace_capsule import TraceCapsule, get_or_create_capsule
from .tracer import SpanContext, Tracer
from .utils import load_config_from_env

# ============================================================================
# INTELLIGENCE & OUTCOME ROUTING (v1.2.0)
# ============================================================================
from .intelligence import (
    KalibrIntelligence,
    get_policy,
    report_outcome,
    get_recommendation,
    register_path,
    decide,
)

if os.getenv("KALIBR_AUTO_INSTRUMENT", "true").lower() == "true":
    # Setup OpenTelemetry collector
    try:
        setup_collector(
            service_name=os.getenv("KALIBR_SERVICE_NAME", "kalibr"),
            file_export=True,
            console_export=os.getenv("KALIBR_CONSOLE_EXPORT", "false").lower() == "true",
        )
    except Exception as e:
        print(f"⚠️  Failed to setup OpenTelemetry collector: {e}")

    # Auto-instrument available SDKs
    try:
        auto_instrument(["openai", "anthropic", "google"])
    except Exception as e:
        print(f"⚠️  Failed to auto-instrument SDKs: {e}")

__all__ = [
    # ========================================================================
    # OBSERVABILITY & TRACING
    # ========================================================================
    # Simple tracing API (recommended)
    "trace",
    # Capsule propagation (Phase 6)
    "TraceCapsule",
    "get_or_create_capsule",
    # Client
    "KalibrClient",
    # Context
    "trace_context",
    "get_trace_id",
    "get_parent_span_id",
    "new_trace_id",
    # Goal Context (v1.3.0)
    "goal",
    "set_goal",
    "get_goal",
    "clear_goal",
    # Tracer
    "Tracer",
    "SpanContext",
    # Cost Adapters
    "BaseCostAdapter",
    "OpenAICostAdapter",
    "AnthropicCostAdapter",
    "CostAdapterFactory",
    # Models
    "TraceConfig",
    "EventData",
    # Utils
    "load_config_from_env",
    # ========================================================================
    # PHASE 1: SDK INSTRUMENTATION & OPENTELEMETRY (v1.1.0)
    # ========================================================================
    # Auto-instrumentation
    "auto_instrument",
    "get_instrumented_providers",
    # OpenTelemetry collector
    "setup_collector",
    "get_tracer_provider",
    "is_collector_configured",
    # ========================================================================
    # INTELLIGENCE & OUTCOME ROUTING (v1.2.0)
    # ========================================================================
    "KalibrIntelligence",
    "get_policy",
    "report_outcome",
    "get_recommendation",
    "register_path",
    "decide",
]
