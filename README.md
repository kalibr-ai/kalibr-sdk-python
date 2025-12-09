<div align="center">

<img src="public/kalibr_logo.png" alt="Kalibr" width="120" />

# Kalibr

**Execution intelligence for AI agents**

See every LLM call. Track every dollar. Debug any failure.

[Website](https://kalibr.systems) · [Docs](https://kalibr.systems/docs) · [Dashboard](https://dashboard.kalibr.systems)

[![PyPI](https://img.shields.io/pypi/v/kalibr?color=blue)](https://pypi.org/project/kalibr/)
[![Downloads](https://img.shields.io/pypi/dm/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/kalibr-ai/kalibr-sdk-python?style=social)](https://github.com/kalibr-ai/kalibr-sdk-python)

</div>

---
```python
from kalibr import auto_instrument
auto_instrument()

# That's it. Every LLM call is now traced.
```

---

## Install
```bash
pip install kalibr
```

## Quick Start

### Auto-Instrumentation

Works with OpenAI, Anthropic, and Google. No code changes required.
```python
from kalibr import auto_instrument
from openai import OpenAI

auto_instrument()

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)

# ✓ Traced
# ✓ Cost calculated
# ✓ Tokens counted
# ✓ Latency measured
```

### Manual Tracing

For custom functions and complex workflows:
```python
from kalibr import trace

@trace(vendor="openai", model="gpt-4")
def analyze(text: str) -> str:
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": f"Analyze: {text}"}]
    )
    return response.choices[0].message.content
```

## Framework Integrations

### LangChain
```bash
pip install kalibr-langchain
```
```python
from kalibr_langchain import KalibrCallbackHandler
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(callbacks=[KalibrCallbackHandler()])
llm.invoke("What is 2+2?")
```

### CrewAI
```bash
pip install kalibr-crewai
```
```python
from kalibr_crewai import KalibrCrewAIInstrumentor

KalibrCrewAIInstrumentor().instrument()
# All CrewAI agents now traced
```

### OpenAI Agents SDK
```bash
pip install kalibr-openai-agents
```
```python
from kalibr_openai_agents import KalibrTracingProcessor
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="Be helpful")
await Runner.run(
    agent,
    "Hello",
    run_config={"tracing_processors": [KalibrTracingProcessor()]}
)
```

## What You Get

| Metric | Description |
|--------|-------------|
| **Cost** | Per-request and cumulative spend across all providers |
| **Tokens** | Input/output token counts for every call |
| **Latency** | End-to-end timing with millisecond precision |
| **Errors** | Automatic capture with full stack traces |
| **Traces** | Distributed tracing across services |

## Supported Providers

| Provider | Auto | Manual |
|----------|:----:|:------:|
| OpenAI | ✓ | ✓ |
| Anthropic | ✓ | ✓ |
| Google AI | ✓ | ✓ |
| LangChain | ✓ | ✓ |
| CrewAI | ✓ | ✓ |
| OpenAI Agents | ✓ | ✓ |

## Configuration
```bash
export KALIBR_API_KEY=your-api-key
```

| Variable | Description |
|----------|-------------|
| `KALIBR_API_KEY` | Your API key |
| `KALIBR_API_ENDPOINT` | Custom endpoint (optional) |
| `KALIBR_AUTO_INSTRUMENT` | Set `false` to disable (default: `true`) |

## Packages

| Package | Description |
|---------|-------------|
| [`kalibr`](https://pypi.org/project/kalibr/) | Core SDK |
| [`kalibr-langchain`](https://pypi.org/project/kalibr-langchain/) | LangChain integration |
| [`kalibr-crewai`](https://pypi.org/project/kalibr-crewai/) | CrewAI integration |
| [`kalibr-openai-agents`](https://pypi.org/project/kalibr-openai-agents/) | OpenAI Agents integration |

## Links

- [Documentation](https://kalibr.systems/docs)
- [Dashboard](https://dashboard.kalibr.systems)
- [GitHub Issues](https://github.com/kalibr-ai/kalibr-sdk-python/issues)

## License

Apache 2.0
