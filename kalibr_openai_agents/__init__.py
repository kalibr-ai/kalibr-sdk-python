"""Kalibr OpenAI Agents SDK Integration - Observability for OpenAI Agents.

This package provides a TracingProcessor that integrates OpenAI's Agents SDK
with Kalibr's observability platform, capturing:
- Agent executions and handoffs
- LLM generation spans with tokens and model info
- Function/tool invocations
- Guardrail checks
- Full trace hierarchy

Usage:
    from kalibr_openai_agents import KalibrTracingProcessor, setup_kalibr_tracing
    from agents import Agent, Runner

    # Option 1: Quick setup (adds to existing processors)
    setup_kalibr_tracing(tenant_id="my-tenant")

    # Option 2: Manual setup with more control
    from agents.tracing import add_trace_processor
    processor = KalibrTracingProcessor(tenant_id="my-tenant")
    add_trace_processor(processor)

    # Use OpenAI Agents normally
    agent = Agent(name="Assistant", instructions="You are helpful.")
    result = Runner.run_sync(agent, "Hello!")

Environment Variables:
    KALIBR_API_KEY: API key for authentication
    KALIBR_COLLECTOR_URL: Backend endpoint URL
    KALIBR_TENANT_ID: Tenant identifier
    KALIBR_ENVIRONMENT: Environment (prod/staging/dev)
    KALIBR_SERVICE: Service name
"""

__version__ = "0.1.0"

from .processor import KalibrTracingProcessor, setup_kalibr_tracing

__all__ = [
    "KalibrTracingProcessor",
    "setup_kalibr_tracing",
    "__version__",
]
