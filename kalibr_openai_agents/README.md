# Kalibr OpenAI Agents SDK Integration

Observability integration for OpenAI's Agents SDK using the Kalibr platform.

## Features

- **TracingProcessor implementation** for seamless integration
- **Automatic span capture** for agents, generations, functions, handoffs, guardrails
- **Token and cost tracking** for LLM generations
- **Trace hierarchy** preservation
- **Error tracking** with context
- **Batched telemetry** for efficiency

## Installation

```bash
pip install kalibr[openai-agents]
```

## Quick Start

### Option 1: Quick Setup (Recommended)

```python
from kalibr_openai_agents import setup_kalibr_tracing
from agents import Agent, Runner

# One-line setup - adds Kalibr processor to existing processors
setup_kalibr_tracing(tenant_id="my-tenant")

# Use OpenAI Agents normally
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
)

result = Runner.run_sync(agent, "What is the capital of France?")
print(result.final_output)
```

### Option 2: Manual Setup

```python
from kalibr_openai_agents import KalibrTracingProcessor
from agents import Agent, Runner
from agents.tracing import add_trace_processor

# Create processor with custom configuration
processor = KalibrTracingProcessor(
    api_key="your-api-key",
    tenant_id="my-tenant",
    environment="prod",
    service="my-agents-app",
)

# Add to OpenAI Agents SDK
add_trace_processor(processor)

# Use agents
agent = Agent(name="Assistant", instructions="...")
result = Runner.run_sync(agent, "Hello!")
```

## Configuration

### Environment Variables

```bash
export KALIBR_API_KEY="your-api-key"
export KALIBR_COLLECTOR_URL="https://api.kalibr.systems/api/ingest"
export KALIBR_TENANT_ID="my-tenant"
export KALIBR_ENVIRONMENT="prod"
export KALIBR_SERVICE="openai-agents-app"
export KALIBR_WORKFLOW_ID="my-workflow"
```

### Constructor Parameters

```python
processor = KalibrTracingProcessor(
    api_key="...",              # API key for authentication
    endpoint="...",             # Backend endpoint URL
    tenant_id="...",            # Tenant identifier
    environment="prod",         # Environment (prod/staging/dev)
    service="my-app",           # Service name
    workflow_id="my-workflow",  # Workflow identifier
    capture_input=True,         # Capture span inputs
    capture_output=True,        # Capture span outputs
)
```

## What Gets Traced

The processor captures all OpenAI Agents SDK span types:

| Span Type | Operation | Data Captured |
|-----------|-----------|---------------|
| Generation | `llm_generation` | Model, tokens, cost, input/output |
| Agent | `agent:{name}` | Agent name, duration |
| Function | `function:{name}` | Function name, input/output |
| Handoff | `handoff:{from}->{to}` | Agent transfer info |
| Guardrail | `guardrail:{name}` | Guardrail check result |
| Trace | `trace:{workflow}` | Workflow name, span count |

## Event Schema

Events follow Kalibr's v1.0 schema:

```json
{
  "schema_version": "1.0",
  "trace_id": "trace_abc123...",
  "span_id": "span_xyz789...",
  "parent_span_id": "span_parent...",
  "provider": "openai",
  "model_id": "gpt-4o",
  "operation": "llm_generation",
  "duration_ms": 1250,
  "input_tokens": 150,
  "output_tokens": 75,
  "cost_usd": 0.003375,
  "status": "success",
  "metadata": {
    "span_type": "generation",
    "openai_agents": true
  }
}
```

## Multi-Agent Example

```python
from kalibr_openai_agents import setup_kalibr_tracing
from agents import Agent, Runner

setup_kalibr_tracing(tenant_id="my-tenant")

# Create multiple agents
researcher = Agent(
    name="Researcher",
    instructions="You research topics thoroughly.",
)

writer = Agent(
    name="Writer",
    instructions="You write clear content.",
    handoff_description="Writes content based on research.",
)

# Run with handoffs
result = Runner.run_sync(
    researcher,
    "Research and write about quantum computing",
)

# All agents and handoffs are traced
```

## Combining with Other Integrations

If you're using both OpenAI Agents and LangChain:

```python
from kalibr_openai_agents import setup_kalibr_tracing
from kalibr_langchain import KalibrCallbackHandler

# Setup both
setup_kalibr_tracing(tenant_id="my-tenant")
langchain_handler = KalibrCallbackHandler(tenant_id="my-tenant")

# Both frameworks will send telemetry to Kalibr
```

## Best Practices

1. **Call setup early** - Configure tracing before creating agents
2. **Use workflow_id** - Group related traces together
3. **Consider capture settings** - Disable input/output capture for sensitive data
4. **Flush on shutdown** - Call `processor.force_flush()` before exit

## Processor Lifecycle Methods

```python
processor = KalibrTracingProcessor(...)

# Force flush pending events
processor.force_flush()

# Shutdown and cleanup
processor.shutdown()
```

## License

Apache 2.0 - see the main Kalibr SDK [LICENSE](../LICENSE) for details.
