# Kalibr Python SDK

Production-grade observability and intelligence for LLM applications. Automatically instrument OpenAI, Anthropic, and Google AI SDKs with zero code changes.

[![PyPI version](https://img.shields.io/pypi/v/kalibr)](https://pypi.org/project/kalibr/)
[![Python](https://img.shields.io/pypi/pyversions/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Features

- **Zero-code instrumentation** — Automatic tracing for OpenAI, Anthropic, and Google AI
- **Outcome-conditioned routing** — Query optimal models based on historical success rates
- **Cross-agent tracing** — TraceCapsule propagates context across service boundaries
- **Cost & token tracking** — Real-time cost calculation and token monitoring
- **Framework integrations** — LangChain, CrewAI, OpenAI Agents SDK

## Installation

```bash
pip install kalibr
```

## Quick Start

### Auto-instrumentation (Recommended)

Simply import `kalibr` at the start of your application—all LLM calls are automatically traced:

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

### Manual Tracing with Decorator

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

Query Kalibr for optimal model recommendations based on real execution data and historical success rates.

### Query for Optimal Model

```python
from kalibr import get_policy

# Get the best model for a specific goal
policy = get_policy(goal="book_meeting")
print(f"Use model: {policy.model_id}, provider: {policy.provider}")
```

### Report Outcomes

Help Kalibr learn from your executions by reporting outcomes:

```python
from kalibr import report_outcome, get_trace_id

# After an LLM call, report whether it succeeded
trace_id = get_trace_id()
report_outcome(
    trace_id=trace_id,
    goal="book_meeting",
    success=True
)
```

### Direct API Access

For advanced use cases, use the `KalibrIntelligence` class directly:

```python
from kalibr import KalibrIntelligence

intel = KalibrIntelligence(
    api_key="your-kalibr-api-key",
    tenant_id="your-tenant-id"
)

# Get recommendation with optimization target
rec = intel.get_recommendation(
    goal="summarization",
    optimize_for="balanced"
)

print(f"Recommended: {rec.model_id} (confidence: {rec.confidence})")
```

### Optimization Targets

| Target | Description |
|--------|-------------|
| `cost` | Minimize cost while maintaining quality |
| `quality` | Maximize output quality |
| `latency` | Minimize response time |
| `balanced` | Equal weighting across all factors (default) |
| `outcome` | Maximize success rate based on historical data |

## TraceCapsule

TraceCapsule enables cross-agent tracing by propagating context across service boundaries.

### Basic Usage

```python
from kalibr import get_or_create_capsule

# Get or create a capsule for the current trace
capsule = get_or_create_capsule()

# Append a hop when making an LLM call
capsule.append_hop(
    provider="openai",
    model="gpt-4o",
    cost_usd=0.002,
    latency_ms=450
)

# Convert to JSON for HTTP header propagation
header_value = capsule.to_json()
# Add to outgoing request: headers["X-Kalibr-Capsule"] = header_value
```

### Cross-Service Propagation

```python
import requests
from kalibr import get_or_create_capsule

capsule = get_or_create_capsule()
capsule.append_hop(provider="anthropic", model="claude-3-5-sonnet-20241022", cost_usd=0.003, latency_ms=320)

# Propagate to downstream service
response = requests.post(
    "https://api.example.com/process",
    headers={"X-Kalibr-Capsule": capsule.to_json()},
    json={"data": "..."}
)
```

> **Note:** TraceCapsule maintains a rolling window of the last 5 hops to keep payload size manageable.

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

# Instrument all CrewAI agents
instrumentor = KalibrCrewAIInstrumentor()
instrumentor.instrument()

# Now create and run your crew as normal
from crewai import Agent, Task, Crew

agent = Agent(role="Researcher", goal="Research topics", backstory="...")
task = Task(description="Research AI trends", agent=agent)
crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
```

See [CrewAI Integration Guide](kalibr_crewai/README.md) for full documentation.

### OpenAI Agents SDK

```bash
pip install kalibr[openai-agents]
```

```python
from kalibr_openai_agents import setup_kalibr_tracing

# Enable tracing for OpenAI Agents
setup_kalibr_tracing()

# Now use OpenAI Agents as normal
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are a helpful assistant.")
result = Runner.run_sync(agent, "Hello!")
```

See [OpenAI Agents Integration Guide](kalibr_openai_agents/README.md) for full documentation.

## Configuration

Configure via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `KALIBR_API_KEY` | API key for authentication | *Required* |
| `KALIBR_COLLECTOR_URL` | Collector endpoint URL | `https://api.kalibr.systems/api/v1/traces` |
| `KALIBR_TENANT_ID` | Tenant identifier | `default` |
| `KALIBR_WORKFLOW_ID` | Workflow identifier | `default` |
| `KALIBR_SERVICE_NAME` | Service name for spans | `kalibr-app` |
| `KALIBR_ENVIRONMENT` | Environment (prod/staging/dev) | `prod` |
| `KALIBR_AUTO_INSTRUMENT` | Enable auto-instrumentation | `true` |
| `KALIBR_INTELLIGENCE_URL` | Intelligence API endpoint | `https://api.kalibr.systems/api/v1/intelligence` |

## CLI Commands

```bash
# Start a local development server with tracing
kalibr serve myapp.py

# Run your app with managed runtime lifecycle
kalibr run myapp.py --port 8000

# Deploy to cloud platforms
kalibr deploy myapp.py --runtime fly.io

# Fetch trace capsule data by ID
kalibr capsule <trace-id>

# Show SDK version
kalibr version
```

## Supported Providers

| Provider | Models | Auto-Instrumentation |
|----------|--------|---------------------|
| OpenAI | GPT-4, GPT-4o, GPT-4o-mini, o1, o1-mini | Yes |
| Anthropic | Claude 3.5 Sonnet, Claude 3 Opus, Sonnet, Haiku | Yes |
| Google | Gemini Pro, Gemini Flash, Gemini Ultra | Yes |

## Examples

See the [`examples/`](./examples) directory:

- `basic_example.py` — Simple auto-instrumentation
- `basic_agent.py` — Agent with tracing
- `cross_vendor.py` — Multi-provider workflows
- `outcome_routing.py` — Outcome-conditioned model selection
- `trace_capsule.py` — Cross-service trace propagation

## Development

```bash
git clone https://github.com/kalibr-ai/kalibr-sdk-python.git
cd kalibr-sdk-python

pip install -e ".[dev]"

# Run tests
pytest

# Format code
black kalibr/

# Lint code
ruff check kalibr/
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Links

- [Documentation](https://docs.kalibr.systems)
- [Dashboard](https://dashboard.kalibr.systems)
- [GitHub](https://github.com/kalibr-ai/kalibr-sdk-python)
- [TypeScript SDK](https://github.com/kalibr-ai/kalibr-sdk-ts)
- [PyPI](https://pypi.org/project/kalibr/)
