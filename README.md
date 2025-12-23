# Kalibr Python SDK

Production-grade observability and execution intelligence for LLM applications. Automatically instrument OpenAI, Anthropic, and Google AI SDKs with zero code changes.

[![PyPI version](https://img.shields.io/pypi/v/kalibr)](https://pypi.org/project/kalibr/)
[![Python](https://img.shields.io/pypi/pyversions/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Features

- **Zero-code instrumentation** - Automatic tracing for OpenAI, Anthropic, and Google AI SDKs
- **Outcome-conditioned routing** - Query for optimal models based on historical success rates
- **TraceCapsule** - Cross-agent context propagation for multi-agent systems
- **Cost tracking** - Real-time cost calculation for all LLM calls
- **Token monitoring** - Track input/output tokens across providers
- **Framework integrations** - LangChain, CrewAI, OpenAI Agents SDK

## Installation

```bash
pip install kalibr
```

## Quick Start

### Auto-instrumentation (Recommended)

Simply import `kalibr` at the start of your application - all LLM calls are automatically traced:

```python
import kalibr  # Must be FIRST import
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
# That's it. The call is automatically traced.
```

### Manual Tracing with @trace Decorator

For more control, use the `@trace` decorator:

```python
from kalibr import trace
from openai import OpenAI

@trace(operation="summarize", provider="openai", model="gpt-4o")
def summarize_text(text: str) -> str:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Summarize the following text."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content
```

### Multi-Provider Example

```python
import kalibr
from openai import OpenAI
from anthropic import Anthropic

# Both are automatically traced
openai_client = OpenAI()
anthropic_client = Anthropic()

gpt_response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum computing"}]
)

claude_response = anthropic_client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain machine learning"}]
)
```

## Outcome-Conditioned Routing

Query Kalibr for optimal model recommendations based on real execution outcomes:

```python
from kalibr import get_policy, report_outcome

# Before executing - get the best model for your goal
policy = get_policy(goal="book_meeting")
print(f"Use {policy['recommended_model']} - {policy['outcome_success_rate']:.0%} success rate")

# Execute with the recommended model
# ...

# After executing - report what happened
report_outcome(
    trace_id="abc123",
    goal="book_meeting",
    success=True
)
```

### With Constraints

```python
from kalibr import get_policy

policy = get_policy(
    goal="resolve_ticket",
    constraints={
        "max_cost_usd": 0.05,
        "max_latency_ms": 3000,
        "min_quality": 0.8
    }
)
```

## TraceCapsule - Cross-Agent Tracing

Propagate trace context across agent boundaries:

```python
from kalibr import TraceCapsule, get_or_create_capsule

# Agent 1: Create capsule and add hop
capsule = get_or_create_capsule()
capsule.add_hop(
    agent_id="agent-1",
    model="gpt-4o",
    latency_ms=150,
    cost_usd=0.002
)

# Pass to Agent 2 via HTTP header
headers = {"X-Kalibr-Capsule": capsule.to_header()}

# Agent 2: Receive and continue
capsule = TraceCapsule.from_header(headers["X-Kalibr-Capsule"])
capsule.add_hop(agent_id="agent-2", model="claude-3-5-sonnet-20241022", ...)
```

## Framework Integrations

### LangChain

```bash
pip install kalibr[langchain]
```

```python
from kalibr_langchain import KalibrCallbackHandler
from langchain_openai import ChatOpenAI

handler = KalibrCallbackHandler()
llm = ChatOpenAI(model="gpt-4o", callbacks=[handler])
response = llm.invoke("What is the capital of France?")
```

See [LangChain Integration Guide](kalibr_langchain/README.md) for full documentation.

### CrewAI

```bash
pip install kalibr[crewai]
```

```python
from kalibr_crewai import KalibrCrewAIInstrumentor
from crewai import Agent, Task, Crew

instrumentor = KalibrCrewAIInstrumentor()
instrumentor.instrument()

# Use CrewAI normally - all operations are traced
```

See [CrewAI Integration Guide](kalibr_crewai/README.md) for full documentation.

### OpenAI Agents SDK

```bash
pip install kalibr[openai-agents]
```

```python
from kalibr_openai_agents import setup_kalibr_tracing
from agents import Agent, Runner

setup_kalibr_tracing()

agent = Agent(name="Assistant", instructions="You are helpful.")
result = Runner.run_sync(agent, "Hello!")
```

See [OpenAI Agents Integration Guide](kalibr_openai_agents/README.md) for full documentation.

## Configuration

Configure via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `KALIBR_API_KEY` | API key for authentication | *Required* |
| `KALIBR_TENANT_ID` | Tenant identifier | `default` |
| `KALIBR_COLLECTOR_URL` | Collector endpoint URL | `https://api.kalibr.systems/api/ingest` |
| `KALIBR_INTELLIGENCE_URL` | Intelligence API URL | `https://kalibr-intelligence.fly.dev` |
| `KALIBR_SERVICE_NAME` | Service name for spans | `kalibr-app` |
| `KALIBR_ENVIRONMENT` | Environment (prod/staging/dev) | `prod` |
| `KALIBR_WORKFLOW_ID` | Workflow identifier | `default` |
| `KALIBR_AUTO_INSTRUMENT` | Enable auto-instrumentation | `true` |

## CLI Commands

```bash
# Serve your app with tracing
kalibr serve myapp.py

# Run with managed runtime
kalibr run myapp.py --port 8000

# Deploy to cloud platforms
kalibr deploy myapp.py --runtime fly.io

# Fetch trace capsule by ID
kalibr capsule <trace-id>

# Show version
kalibr version
```

## Supported Providers

| Provider | Models | Auto-Instrumentation |
|----------|--------|---------------------|
| OpenAI | GPT-4, GPT-4o, GPT-3.5 | Yes |
| Anthropic | Claude 3.5 Sonnet, Claude 3 Opus/Sonnet/Haiku | Yes |
| Google | Gemini Pro, Gemini Flash | Yes |

## Development

```bash
git clone https://github.com/kalibr-ai/kalibr-sdk-python.git
cd kalibr-sdk-python

pip install -e ".[dev]"

# Run tests
pytest

# Format code
black kalibr/
ruff check kalibr/
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0 - see [LICENSE](LICENSE).

## Links

- [Documentation](https://docs.kalibr.systems)
- [Dashboard](https://dashboard.kalibr.systems)
- [GitHub](https://github.com/kalibr-ai/kalibr-sdk-python)
- [PyPI](https://pypi.org/project/kalibr/)
