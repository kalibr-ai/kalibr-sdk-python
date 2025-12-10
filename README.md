# Kalibr Python SDK

Production-grade observability for LLM applications. Automatically instrument OpenAI, Anthropic, and Google AI SDKs with zero code changes.

## Features

- **Zero-code instrumentation** - Automatic tracing for OpenAI, Anthropic, and Google AI
- **Cost tracking** - Real-time cost calculation for all LLM calls
- **Token monitoring** - Track input/output tokens across providers
- **Parent-child traces** - Automatic trace relationship management
- **Multi-provider support** - Works with GPT-4, Claude, Gemini, and more

## Installation

```bash
pip install kalibr
```

## Quick Start

### Auto-instrumentation (Recommended)

Simply import `kalibr` at the start of your application - all LLM calls are automatically traced:

```python
import kalibr  # Enable auto-instrumentation
import openai

# Set your Kalibr API key
import os
os.environ["KALIBR_API_KEY"] = "your-kalibr-api-key"

# All OpenAI calls are now automatically traced
client = openai.OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Manual Tracing with Decorator

For more control, use the `@trace` decorator:

```python
from kalibr import trace
import openai

@trace(operation="summarize", provider="openai", model="gpt-4o")
def summarize_text(text: str) -> str:
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Summarize the following text."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content

result = summarize_text("Your long text here...")
```

### Multi-Provider Example

```python
import kalibr
import openai
import anthropic

# OpenAI call - automatically traced
openai_client = openai.OpenAI()
gpt_response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum computing"}]
)

# Anthropic call - automatically traced
anthropic_client = anthropic.Anthropic()
claude_response = anthropic_client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain machine learning"}]
)
```

## Configuration

Configure the SDK using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `KALIBR_API_KEY` | API key for authentication | *Required* |
| `KALIBR_COLLECTOR_URL` | Collector endpoint URL | `http://localhost:8001/api/ingest` |
| `KALIBR_TENANT_ID` | Tenant identifier for multi-tenant setups | `default` |
| `KALIBR_WORKFLOW_ID` | Workflow identifier for grouping traces | `default` |
| `KALIBR_SERVICE_NAME` | Service name for OpenTelemetry spans | `kalibr-app` |
| `KALIBR_ENVIRONMENT` | Environment (prod, staging, dev) | `prod` |
| `KALIBR_AUTO_INSTRUMENT` | Enable/disable auto-instrumentation | `true` |
| `KALIBR_CONSOLE_EXPORT` | Enable console span export for debugging | `false` |

## CLI Tools

The SDK includes command-line tools for running and deploying applications:

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

## Examples

See the [`examples/`](./examples) directory for complete examples:

- `basic_example.py` - Simple tracing example
- `basic_agent.py` - Agent with auto-instrumentation
- `advanced_example.py` - Advanced tracing patterns
- `cross_vendor.py` - Multi-provider workflows
- `test_mas.py` - Multi-agent system demonstration

## Development

```bash
# Clone the repository
git clone https://github.com/kalibr-ai/kalibr-sdk-python.git
cd kalibr-sdk-python

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black kalibr/
ruff check kalibr/
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](./LICENSE) for details.

## Links

- [Documentation](https://docs.kalibr.systems)
- [GitHub Issues](https://github.com/kalibr-ai/kalibr-sdk-python/issues)
- [PyPI Package](https://pypi.org/project/kalibr/)
