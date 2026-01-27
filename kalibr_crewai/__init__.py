"""Kalibr CrewAI Integration - Observability for CrewAI applications.

This package provides callbacks and auto-instrumentation for CrewAI,
capturing:
- Agent step execution with tool calls
- Task completion with outputs
- Crew execution lifecycle
- Token usage and costs
- Error tracking

Usage with Callbacks:
    from kalibr_crewai import KalibrAgentCallback, KalibrTaskCallback
    from crewai import Agent, Task, Crew

    # Create callbacks
    agent_callback = KalibrAgentCallback(tenant_id="my-tenant")
    task_callback = KalibrTaskCallback(tenant_id="my-tenant")

    # Use with Agent
    agent = Agent(
        role="Researcher",
        goal="Find information",
        step_callback=agent_callback,
    )

    # Use with Task
    task = Task(
        description="Research AI trends",
        agent=agent,
        callback=task_callback,
    )

Usage with Auto-Instrumentation:
    from kalibr_crewai import KalibrCrewAIInstrumentor

    # Instrument CrewAI (call before creating crews)
    instrumentor = KalibrCrewAIInstrumentor(tenant_id="my-tenant")
    instrumentor.instrument()

    # Now all CrewAI operations are automatically traced
    crew = Crew(agents=[...], tasks=[...])
    result = crew.kickoff()

    # Optionally uninstrument
    instrumentor.uninstrument()

Environment Variables:
    KALIBR_API_KEY: API key for authentication
    KALIBR_COLLECTOR_URL: Backend endpoint URL
    KALIBR_TENANT_ID: Tenant identifier
    KALIBR_ENVIRONMENT: Environment (prod/staging/dev)
    KALIBR_SERVICE: Service name
"""

__version__ = "0.1.0"

from .callbacks import KalibrAgentCallback, KalibrTaskCallback
from .instrumentor import KalibrCrewAIInstrumentor

__all__ = [
    "KalibrAgentCallback",
    "KalibrTaskCallback",
    "KalibrCrewAIInstrumentor",
    "__version__",
]
