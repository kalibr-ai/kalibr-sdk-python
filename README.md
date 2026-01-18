# Kalibr

Adaptive routing for AI agents. Kalibr learns which models work best for your tasks and routes automatically.

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
    goal="extract_company",
    paths=["gpt-4o", "claude-sonnet-4-20250514"]
)

response = router.completion(
    messages=[{"role": "user", "content": "Extract the company: Hi, I'm Sarah from Stripe."}]
)

router.report(success=True)
```

Kalibr picks the best model, makes the call, and learns from the outcome.

## How It Works

1. **You define paths** - models (and optionally tools/params) that can handle your task
2. **Kalibr picks** - uses Thompson Sampling to balance exploration vs exploitation
3. **You report outcomes** - tell Kalibr if it worked
4. **Kalibr learns** - routes more traffic to what works

## Paths

A path is a model + optional tools + optional params:
```python
# Just models
paths = ["gpt-4o", "claude-sonnet-4-20250514", "gpt-4o-mini"]

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

## Advanced Path Configuration

### Routing Between Parameters

Kalibr can route between different parameter configurations of the same model:
```python
from kalibr import Router

router = Router(
    goal="creative_writing",
    paths=[
        {"model": "gpt-4o", "params": {"temperature": 0.3}},
        {"model": "gpt-4o", "params": {"temperature": 0.9}},
        {"model": "claude-sonnet-4-20250514", "params": {"temperature": 0.7}}
    ]
)

response = router.completion(messages=[...])
router.report(success=True)
```

Each unique `(model, params)` combination is tracked separately. Kalibr learns which configuration works best for your specific goal.

### Routing Between Tools
```python
router = Router(
    goal="research_task",
    paths=[
        {"model": "gpt-4o", "tools": ["web_search"]},
        {"model": "gpt-4o", "tools": ["code_interpreter"]},
        {"model": "claude-sonnet-4-20250514"}
    ]
)
```

### When to Use get_policy() Instead of Router

For most use cases, use `Router`. It handles provider dispatching and response conversion automatically.

Use `get_policy()` for advanced scenarios:
- Integrating with frameworks like LangChain that wrap LLM calls
- Custom retry logic or provider-specific features
- Building tools that need fine-grained control
```python
from kalibr import get_policy, report_outcome

policy = get_policy(goal="summarize")
model = policy["recommended_model"]

# You call the provider yourself
if model.startswith("gpt"):
    client = OpenAI()
    response = client.chat.completions.create(model=model, messages=[...])

report_outcome(trace_id=trace_id, goal="summarize", success=True)
```

## Outcome Reporting

### Automatic (with success_when)
```python
router = Router(
    goal="summarize",
    paths=["gpt-4o", "claude-sonnet-4-20250514"],
    success_when=lambda output: len(output) > 100
)

response = router.completion(messages=[...])
# Outcome reported automatically based on success_when
```

### Manual
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

Kalibr auto-instruments OpenAI, Anthropic, and Google SDKs on import:
```python
import kalibr  # Must be first import
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(model="gpt-4o", messages=[...])
# Traced automatically
```

Disable with `KALIBR_AUTO_INSTRUMENT=false`.

## Low-Level API

For advanced use cases, you can use the intelligence API directly:
```python
from kalibr import register_path, decide, report_outcome

# Register paths
register_path(goal="book_meeting", model_id="gpt-4o")
register_path(goal="book_meeting", model_id="claude-sonnet-4-20250514")

# Get routing decision
decision = decide(goal="book_meeting")
model = decision["model_id"]

# Make your own LLM call, then report
report_outcome(trace_id="...", goal="book_meeting", success=True)
```

## Other Integrations
```bash
pip install kalibr[crewai]        # CrewAI
pip install kalibr[openai-agents] # OpenAI Agents SDK
pip install kalibr[langchain-all] # LangChain with all providers
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `KALIBR_API_KEY` | API key from dashboard | Required |
| `KALIBR_TENANT_ID` | Tenant ID from dashboard | Required |
| `KALIBR_AUTO_INSTRUMENT` | Auto-instrument LLM SDKs | `true` |
| `KALIBR_INTELLIGENCE_URL` | Intelligence service URL | `https://kalibr-intelligence.fly.dev` |

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

- [Docs](https://kalibr.dev/docs)
- [Dashboard](https://dashboard.kalibr.systems)
- [GitHub](https://github.com/kalibr-ai/kalibr-sdk-python)
