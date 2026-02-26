# Kalibr — Ship agents that fix themselves

Your agent captures its own execution telemetry, reports whether it achieved
the customer's goal, and Kalibr routes future calls to what actually works.
When models degrade, Kalibr reroutes before users notice.

**Install:** `pip install kalibr`

**Required env vars:**
- `KALIBR_API_KEY` — get from dashboard.kalibr.systems/settings
- `KALIBR_TENANT_ID` — get from dashboard.kalibr.systems/settings

**Or use autonomous provisioning:**
- `KALIBR_PROVISIONING_TOKEN` — create at dashboard.kalibr.systems/settings
- Then run `kalibr init` — credentials provisioned automatically

## Quick Start
```python
from kalibr import Router

router = Router(
    goal="extract_company",
    paths=["gpt-4o", "claude-sonnet-4-20250514"],
    success_when=lambda output: "company" in output.lower()
)

response = router.completion(
    messages=[{"role": "user", "content": "Extract the company: Hi from Stripe."}]
)
```

## CLI
```bash
kalibr init      # scan codebase, wrap bare LLM calls with Router
kalibr verify    # check credentials
kalibr prompt    # copy Claude Code integration prompt to clipboard
```

**Links:** [Docs](https://kalibr.systems/docs) · [Dashboard](https://dashboard.kalibr.systems) · [GitHub](https://github.com/kalibr-ai/kalibr-sdk-python)

[![PyPI](https://img.shields.io/pypi/v/kalibr)](https://pypi.org/project/kalibr/)
[![Python](https://img.shields.io/pypi/pyversions/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

---

Kalibr learns what's working as your agents run in production and routes them around failures, degradations, and cost spikes before you know they're happening. Define your execution paths (model + tools + params), tell Kalibr what success looks like, and it handles the rest.

Observability shows you the problem. Kalibr fixes it.

**Open source SDK. Hosted intelligence.**

## Installation

```bash
pip install kalibr
```

For accurate token counting:
```bash
pip install kalibr[tokens]
```

## Setup

Get your credentials from [dashboard.kalibr.systems/settings](https://dashboard.kalibr.systems/settings), then:
```bash
export KALIBR_API_KEY=your-api-key
export KALIBR_TENANT_ID=your-tenant-id
export OPENAI_API_KEY=sk-...  # or ANTHROPIC_API_KEY for Claude models
```

## How It Works

Every call your agent makes generates data. Kalibr uses that data to get better.

1. **You define paths** — models, tools, and parameters that can handle your task
2. **Kalibr picks** — routes to what's been working, while exploring alternatives
3. **You report outcomes** — tell Kalibr what success looks like (or it figures it out from your `success_when` lambda)
4. **Kalibr adapts** — routes more traffic to what works, routes around what doesn't

No dashboards to watch. No alerts to triage. Your agent improves itself.

## Paths

A path is any combination of model + tools + params. Kalibr tracks each combination separately and learns which one works best for each goal.

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

# Mix and match
paths = [
    {"model": "gpt-4o", "tools": ["web_search"], "params": {"temperature": 0.3}},
    {"model": "claude-sonnet-4-20250514", "params": {"temperature": 0.7}},
    "gpt-4o-mini"
]
```

This is what makes Kalibr different from model routers. OpenRouter picks a model. Kalibr picks the full execution path — and knows whether it actually worked.

## Outcome Reporting

### Automatic (recommended)
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

## Framework Integrations

### LangChain
```bash
pip install kalibr[langchain]
```
```python
from kalibr import Router

router = Router(goal="summarize", paths=["gpt-4o", "claude-sonnet-4-20250514"])
llm = router.as_langchain()

chain = prompt | llm | parser
```

### All integrations
```bash
pip install kalibr[crewai]        # CrewAI
pip install kalibr[openai-agents] # OpenAI Agents SDK
pip install kalibr[langchain-all] # LangChain with all providers
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

Use `get_policy()` when you need fine-grained control — custom retry logic, framework integrations, or provider-specific features:

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

Or go even lower:
```python
from kalibr import register_path, decide, report_outcome

register_path(goal="book_meeting", model_id="gpt-4o")
register_path(goal="book_meeting", model_id="claude-sonnet-4-20250514")

decision = decide(goal="book_meeting")
model = decision["model_id"]

# Make your own LLM call, then report
report_outcome(trace_id="...", goal="book_meeting", success=True)
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

- [Docs](https://kalibr.systems/docs)
- [Dashboard](https://dashboard.kalibr.systems)
- [GitHub](https://github.com/kalibr-ai/kalibr-sdk-python)
