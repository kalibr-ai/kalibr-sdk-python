# Kalibr

Adaptive routing for AI agents. Kalibr learns which models, tools, and configs work best for each task and routes automatically.

[![PyPI](https://img.shields.io/pypi/v/kalibr)](https://pypi.org/project/kalibr/)
[![Python](https://img.shields.io/pypi/pyversions/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Installation
```bash
pip install kalibr
```

## Quick Start
```python
from kalibr import Router

router = Router(
    goal="book_meeting",
    paths=["gpt-4o", "claude-sonnet-4-20250514", "gpt-4o-mini"],
    success_when=lambda output: "confirmed" in output.lower()
)

response = router.completion(
    messages=[{"role": "user", "content": "Book a meeting with John tomorrow"}]
)
```

Kalibr picks the best model, makes the call, checks success, and learns for next time.

## Paths

A path is a model + optional tools + optional params:
```python
# Just models
paths = ["gpt-4o", "claude-sonnet-4-20250514"]

# With tools
paths = [
    {"model": "gpt-4o", "tools": ["web_search"]},
    {"model": "claude-sonnet-4-20250514", "tools": ["web_search", "browser"]},
]

# With params
paths = [
    {"model": "gpt-4o", "params": {"temperature": 0.7}},
    {"model": "gpt-4o", "params": {"temperature": 0.2}},
]
```

## Manual Outcome Reporting
```python
router = Router(goal="book_meeting", paths=["gpt-4o", "claude-sonnet-4-20250514"])
response = router.completion(messages=[...])

meeting_created = check_calendar_api()
router.report(success=meeting_created)
```

## LangChain Integration
```bash
pip install kalibr[langchain]
```
```python
from kalibr import Router

router = Router(goal="summarize", paths=["gpt-4o", "claude-sonnet-4-20250514"])
llm = router.as_langchain()

chain = prompt | llm | parser
```

## Auto-Instrumentation

Kalibr auto-instruments OpenAI, Anthropic, and Google SDKs when imported:
```python
import kalibr  # Must be first import
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(model="gpt-4o", messages=[...])
# Traced automatically
```

Disable with `KALIBR_AUTO_INSTRUMENT=false`.

## Other Integrations
```bash
pip install kalibr[crewai]        # CrewAI
pip install kalibr[openai-agents] # OpenAI Agents SDK
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `KALIBR_API_KEY` | API key | Required |
| `KALIBR_TENANT_ID` | Tenant ID | `default` |
| `KALIBR_AUTO_INSTRUMENT` | Auto-instrument SDKs | `true` |

## Development
```bash
git clone https://github.com/kalibr-ai/kalibr-sdk-python.git
cd kalibr-sdk-python
pip install -e ".[dev]"
pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0

## Links

- [Docs](https://kalibr.systems/docs)
- [Dashboard](https://dashboard.kalibr.systems)
