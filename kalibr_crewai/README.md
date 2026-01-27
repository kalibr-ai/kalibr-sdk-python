# Kalibr CrewAI Integration

Observability integration for CrewAI applications using the Kalibr platform.

## Features

- **Callback-based tracing** for fine-grained control
- **Auto-instrumentation** for zero-code observability
- **Crew lifecycle tracking** with timing and status
- **Agent step monitoring** including tool calls
- **Task completion capture** with outputs
- **Error tracking** with context

## Installation

```bash
pip install kalibr[crewai]
```

## Quick Start

### Option 1: Auto-Instrumentation (Recommended)

```python
from kalibr_crewai import KalibrCrewAIInstrumentor
from crewai import Agent, Task, Crew

# Instrument before creating crews
instrumentor = KalibrCrewAIInstrumentor(
    tenant_id="my-tenant",
    environment="prod",
)
instrumentor.instrument()

# Use CrewAI normally - all operations are traced
researcher = Agent(
    role="Researcher",
    goal="Find information",
    backstory="Expert researcher",
)

task = Task(
    description="Research AI trends",
    agent=researcher,
    expected_output="Summary of trends",
)

crew = Crew(agents=[researcher], tasks=[task])
result = crew.kickoff()

# Events automatically sent to Kalibr
```

### Option 2: Callbacks (Fine-grained Control)

```python
from kalibr_crewai import KalibrAgentCallback, KalibrTaskCallback
from crewai import Agent, Task, Crew

# Create callbacks
agent_callback = KalibrAgentCallback(tenant_id="my-tenant")
task_callback = KalibrTaskCallback(tenant_id="my-tenant")

# Attach to agents and tasks
researcher = Agent(
    role="Researcher",
    goal="Find information",
    backstory="Expert researcher",
    step_callback=agent_callback,  # Traces each agent step
)

task = Task(
    description="Research AI trends",
    agent=researcher,
    callback=task_callback,  # Traces task completion
)

crew = Crew(agents=[researcher], tasks=[task])
result = crew.kickoff()
```

## Configuration

### Environment Variables

```bash
export KALIBR_API_KEY="your-api-key"
export KALIBR_COLLECTOR_URL="https://api.kalibr.systems/api/ingest"
export KALIBR_TENANT_ID="my-tenant"
export KALIBR_ENVIRONMENT="prod"
export KALIBR_SERVICE="crewai-app"
export KALIBR_WORKFLOW_ID="my-workflow"
```

### Constructor Parameters

```python
# For callbacks
callback = KalibrAgentCallback(
    api_key="...",
    endpoint="...",
    tenant_id="...",
    environment="prod",
    service="my-app",
    workflow_id="my-workflow",
    metadata={"team": "platform"},
)

# For instrumentor
instrumentor = KalibrCrewAIInstrumentor(
    api_key="...",
    tenant_id="...",
    capture_input=True,   # Capture task descriptions
    capture_output=True,  # Capture task outputs
)
```

## What Gets Traced

### With Auto-Instrumentation

| Component | Event | Data Captured |
|-----------|-------|---------------|
| Crew | `crew:name` | Agents, tasks, duration, status |
| Agent | `agent:role` | Role, goal, task, duration |
| Task | `task:description` | Description, output, duration |

### With Callbacks

| Callback | Event | Data Captured |
|----------|-------|---------------|
| `step_callback` | Agent steps | Tool calls, actions, outputs |
| `task_callback` | Task complete | Description, raw output, agent |

## Event Schema

Events follow Kalibr's v1.0 schema:

```json
{
  "schema_version": "1.0",
  "trace_id": "uuid",
  "span_id": "uuid",
  "provider": "crewai",
  "model_id": "crew|agent|task",
  "operation": "crew:my-crew",
  "duration_ms": 5000,
  "status": "success",
  "metadata": {
    "crewai": true,
    "span_type": "crew",
    "agent_count": 2,
    "task_count": 3
  }
}
```

## Best Practices

1. **Use auto-instrumentation** for simplicity - it captures all operations
2. **Use callbacks** when you need per-agent or per-task customization
3. **Set workflow_id** to group related crew executions
4. **Call flush()** before exit to ensure all events are sent

## Combining with LangChain

If your CrewAI agents use LangChain tools:

```python
from kalibr_crewai import KalibrCrewAIInstrumentor
from kalibr_langchain import KalibrCallbackHandler

# Instrument both
crewai_instrumentor = KalibrCrewAIInstrumentor(tenant_id="my-tenant")
crewai_instrumentor.instrument()

langchain_handler = KalibrCallbackHandler(tenant_id="my-tenant")

# LangChain tools will also be traced
```

## License

Apache 2.0 - see the main Kalibr SDK [LICENSE](../LICENSE) for details.
