# Kalibr Python SDK

Production-grade observability and intelligence for LLM applications. Automatically instrument OpenAI, Anthropic, and Google AI SDKs with zero code changes.

[![PyPI version](https://img.shields.io/pypi/v/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Features

- **Zero-code instrumentation** — Automatic tracing for OpenAI, Anthropic, and Google AI
- **Cost tracking** — Real-time cost calculation for all LLM calls
- **Token monitoring** — Track input/output tokens across providers
- **Parent-child traces** — Automatic trace relationship management
- **Intelligence API** — Query for optimal model recommendations at runtime
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
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain machine learning"}]
)
```

## Intelligence API

Query Kalibr for optimal model recommendations based on real execution data:

```python
from kalibr import KalibrIntelligence

intel = KalibrIntelligence(
    api_key="your-kalibr-api-key",
    tenant_id="your-tenant-id"
)

# Get the best model for a task
rec = intel.get_recommended_llm(
    task_type="summarization",
    optimize_for="reliability"  # or "cost" or "latency" or "balanced"
)

print(f"Recommended: {rec.model_id} (confidence: {rec.confidence})")

# Use the recommended model
client = OpenAI()
response = client.chat.completions.create(
    model=rec.model_id,
    messages=[{"role": "user", "content": "Summarize this document..."}]
)
```

### Optimization Targets

| Target | Description |
|--------|-------------|
| `cost` | Minimize cost while maintaining quality |
| `quality` | Maximize output quality |
| `latency` | Minimize response time |
| `balanced` | Equal weighting (default) |
| `reliability` | Maximize success rate |

### With Constraints

```python
rec = intel.get_recommended_llm(
    task_type="code_generation",
    optimize_for="balanced",
    constraints={
        "max_cost_usd": 0.05,
        "max_latency_ms": 3000,
        "min_quality": 0.8
    }
)
```

### Report Outcomes (Feedback Loop)

Help Kalibr learn from your executions:

```python
intel.report_outcome(
    trace_id="abc-123",
    quality_score=0.9,
    outcome="success"  # or "error" or "timeout"
)
```

## Framework Integrations

### LangChain

```bash
pip install kalibr[langchain]
```

```python
from kalibr.integrations.langchain import KalibrCallbackHandler
from langchain_openai import ChatOpenAI

handler = KalibrCallbackHandler()
llm = ChatOpenAI(model="gpt-4", callbacks=[handler])
response = llm.invoke("What is the capital of France?")
```

### CrewAI

```bash
pip install kalibr[crewai]
```

```python
from kalibr.integrations.crewai import KalibrCrewAIHandler
from crewai import Agent, Task, Crew

handler = KalibrCrewAIHandler()
# Your CrewAI code with automatic tracing
```

### OpenAI Agents SDK

```bash
pip install kalibr[openai-agents]
```

```python
from kalibr.integrations.openai_agents import KalibrAgentTracer
from agents import Agent, Runner

tracer = KalibrAgentTracer()
# Your OpenAI Agents code with automatic tracing
```

## Configuration

Configure via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `KALIBR_API_KEY` | API key for authentication | *Required* |
| `KALIBR_COLLECTOR_URL` | Collector endpoint URL | `https://api.kalibr.systems/api/ingest` |
| `KALIBR_TENANT_ID` | Tenant identifier | `default` |
| `KALIBR_WORKFLOW_ID` | Workflow identifier | `default` |
| `KALIBR_SERVICE_NAME` | Service name for spans | `kalibr-app` |
| `KALIBR_ENVIRONMENT` | Environment (prod/staging/dev) | `prod` |
| `KALIBR_AUTO_INSTRUMENT` | Enable auto-instrumentation | `true` |

## CLI Tools

```bash
# Run your app locally with tracing
kalibr serve myapp.py

# Run with managed runtime lifecycle
kalibr run myapp.py --port 8000

# Deploy to cloud platforms
kalibr deploy myapp.py --runtime fly.io

# Fetch trace data by ID
kalibr capsule <trace-id>
```

## Supported Providers

| Provider | Models | Auto-Instrumentation |
|----------|--------|---------------------|
| OpenAI | GPT-4, GPT-4o, GPT-3.5 | Yes |
| Anthropic | Claude 3 Opus, Sonnet, Haiku | Yes |
| Google | Gemini Pro, Gemini Flash | Yes |
| Cohere | Command, Command-R | Yes |

## Examples

See the [`examples/`](./examples) directory:

- `basic_example.py` — Simple tracing
- `basic_agent.py` — Agent with auto-instrumentation
- `advanced_example.py` — Advanced tracing patterns
- `cross_vendor.py` — Multi-provider workflows

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

Apache 2.0 — see [LICENSE](LICENSE).

## Links

- [Kalibr Dashboard](https://dashboard.kalibr.systems)
- [GitHub](https://github.com/kalibr-ai/kalibr-sdk-python)
- [PyPI](https://pypi.org/project/kalibr/)
