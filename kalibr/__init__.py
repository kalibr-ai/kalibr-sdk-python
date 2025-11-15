"""Kalibr SDK v1.1.0 - Unified LLM Observability & Multi-Model AI Integration Framework

This SDK combines:
1. Full LLM Observability with tracing, cost tracking, and analytics
2. Multi-Model AI Integration (GPT, Claude, Gemini, Copilot)
3. One-line deployment with Docker and runtime router
4. Schema generation for all major AI platforms
5. **NEW in 1.1.0**: Auto-instrumentation of LLM SDKs (OpenAI, Anthropic, Google)

Features:
- **Auto-Instrumentation**: Zero-config tracing of OpenAI, Anthropic, Google SDK calls
- **OpenTelemetry**: OTel-compatible spans with OTLP export
- **Tracing**: Complete telemetry with @trace decorator
- **Cost Tracking**: Multi-vendor cost calculation (OpenAI, Anthropic, etc.)
- **Deployment**: One-command deployment to Fly.io, Render, or local
- **Schema Generation**: Auto-generate schemas for GPT Actions, Claude MCP, Gemini, Copilot
- **Error Handling**: Automatic error capture with stack traces
- **Analytics**: ClickHouse-backed analytics and alerting

Usage - Auto-Instrumentation (NEW):
    from kalibr import Kalibr
    import openai  # Automatically instrumented!

    app = Kalibr(title="My API")

    @app.action("chat", "Chat with GPT")
    def chat(message: str):
        # This OpenAI call is automatically traced!
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": message}]
        )
        return response.choices[0].message.content

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
    kalibr serve my_app.py              # Run locally
    kalibr deploy my_app.py --runtime fly  # Deploy to Fly.io
    kalibr run my_app.py                # Run with auto-tracing
    kalibr version                       # Show version
"""

__version__ = "1.1.0"

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
from .context import get_parent_span_id, get_trace_id, new_trace_id, trace_context
from .cost_adapter import (
    AnthropicCostAdapter,
    BaseCostAdapter,
    CostAdapterFactory,
    OpenAICostAdapter,
)
from .instrumentation import auto_instrument, get_instrumented_providers

# ============================================================================
# SDK & DEPLOYMENT (from 1.0.30)
# ============================================================================
from .kalibr import Kalibr
from .kalibr_app import KalibrApp
from .models import EventData, TraceConfig
from .schemas import (
    generate_copilot_schema,
    generate_gemini_schema,
    generate_mcp_schema,
    get_base_url,
    get_supported_models,
)
from .simple_tracer import trace
from .trace_capsule import TraceCapsule, get_or_create_capsule
from .tracer import SpanContext, Tracer
from .types import FileUpload, Session
from .utils import load_config_from_env

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
    # SDK & DEPLOYMENT
    # ========================================================================
    # SDK Classes
    "Kalibr",
    "KalibrApp",
    # Types
    "FileUpload",
    "Session",
    # Schema Generation
    "get_base_url",
    "generate_mcp_schema",
    "generate_gemini_schema",
    "generate_copilot_schema",
    "get_supported_models",
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
]
