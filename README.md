# Kalibr Python SDK

Kalibr lets agents choose the optimal model + tools for any task, across any modality, as they run in production.

Open source SDK. Hosted optimization intelligence.

## Features

* **Outcome-aware routing** — Routes each goal to the model+tool path that is actually succeeding in production
* **Continuous optimization** — Learns from real outcomes using Thompson Sampling. Adapts as models degrade, tools fail, or costs shift
* **Auto-instrumentation** — Traces OpenAI, Anthropic, and Google AI calls with zero code changes
* **TraceCapsule** — Cross-agent context propagation for multi-agent systems
* **Cost & token tracking** — Real-time cost calculation and token monitoring across all providers
* **Any model, any modality** — Text LLMs, voice, image, embeddings, classification, translation, anything on HuggingFace
* **HuggingFace integration** — One instrumentor covers all 17 task types across every modality
* **Framework integrations** — LangChain, CrewAI, OpenAI Agents SDK

## Developers — hand this to your coding agent

```
pip install kalibr
kalibr auth
kalibr init
kalibr verify
```

Your agent runs `kalibr auth`, your terminal shows a code, you enter it at dashboard.kalibr.systems/link, and the agent handles the rest — credentials, codebase scanning, framework detection, and instrumentation. One approval, zero config.

Already have credentials? Skip signup:

```
pip install kalibr
export KALIBR_API_KEY=sk_...
export KALIBR_TENANT_ID=tenant_...
kalibr init
kalibr verify
```

### If you are an agent reading this

Full autonomous onboarding protocol: [kalibr.systems/llms.txt](https://kalibr.systems/llms.txt) · [kalibr.systems/setup.txt](https://kalibr.systems/setup.txt)

---

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

## Multimodal Routing

Route any ML task, not just text LLMs:

```python
from kalibr import Router

# Transcription
router = Router(
    goal="transcribe_call",
    paths=["openai/whisper-large-v3", "facebook/seamless-m4t-v2-large"],
    success_when=lambda output: len(output) > 50
)
result = router.execute(task="automatic_speech_recognition", input_data=audio_bytes)

# Image generation
router = Router(goal="product_image", paths=["stabilityai/stable-diffusion-xl-base-1.0"])
result = router.execute(task="text_to_image", input_data="a product photo")
```

`pip install kalibr`

[![PyPI version](https://img.shields.io/pypi/v/kalibr)](https://pypi.org/project/kalibr/)
[![Python](https://img.shields.io/pypi/pyversions/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/github/license/kalibr-ai/kalibr-sdk-python)](LICENSE)

---

## Installation

```bash
pip install kalibr

# For accurate token counting
pip install kalibr[tokens]
```

## Setup

Get your credentials from [dashboard.kalibr.systems/settings](https://dashboard.kalibr.systems/settings), then:

```bash
export KALIBR_API_KEY=your-api-key
export KALIBR_TENANT_ID=your-tenant-id
export OPENAI_API_KEY=sk-...  # or ANTHROPIC_API_KEY for Claude models
```

Or use autonomous provisioning:

```bash
export KALIBR_PROVISIONING_TOKEN=your-token  # create at dashboard.kalibr.systems/settings
kalibr init  # scans your project and provisions credentials automatically
```

Or link via device code (recommended):

```bash
kalibr auth
# Terminal shows a code. Enter it at dashboard.kalibr.systems/link.
# Agent receives credentials automatically. No email required.
kalibr init
```

## CLI

```bash
kalibr auth          # link agent to your Kalibr account (device code — recommended)
kalibr signup EMAIL  # DEPRECATED: use kalibr auth instead
kalibr init          # scan codebase, wrap bare LLM calls with Router, provision credentials
kalibr verify        # check credentials and Router connectivity
kalibr prompt        # copy Claude Code / Cursor integration prompt to clipboard
```

## How It Works

Every call your agent makes generates data. Kalibr uses that data to get better.

1. **You define paths** — models, tools, and parameters that can handle your task
2. **Kalibr picks** — uses Thompson Sampling to route to what's been working while exploring alternatives
3. **You report outcomes** — tell Kalibr if it worked (or use `success_when` to automate it)
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

### With failure categories

Tell Kalibr *why* something failed so routing decisions are made against root cause, not just success rate:

```python
from kalibr import FAILURE_CATEGORIES
# ["timeout", "context_exceeded", "tool_error", "rate_limited",
#  "validation_failed", "hallucination_detected", "user_unsatisfied",
#  "empty_response", "malformed_output", "auth_error", "provider_error", "unknown"]

router.report(
    success=False,
    failure_category="rate_limited",
    reason="hit provider limit"
)
# Invalid categories raise ValueError immediately
```

### Update outcomes after the fact

For async validation, user feedback, or downstream system confirmation:

```python
from kalibr import update_outcome

update_outcome(
    trace_id="abc123",
    goal="resolve_ticket",
    success=False,
    failure_reason="customer_reopened",
    failure_category="user_unsatisfied",
    score=0.3,
    metadata={"ticket_id": "T-9182"}
)
```

## Insights API

Query what Kalibr has learned about your goals — health status, failure mode breakdowns, path comparisons, and actionable signals:

```python
from kalibr import get_insights

# All goals, last 7 days
insights = get_insights()

# Specific goal, custom window
insights = get_insights(goal="research_agent", window_hours=24)

for goal_data in insights["goals"]:
    print(goal_data["status"])             # healthy / degraded / insufficient_data
    print(goal_data["top_failure_modes"])
    print(goal_data["actionable_signals"]) # path_underperforming, drift_detected, etc.
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
pip install kalibr[crewai]          # CrewAI
pip install kalibr[openai-agents]   # OpenAI Agents SDK
pip install kalibr[langchain-all]   # LangChain with all providers
```

## Auto-Instrumentation

Kalibr auto-instruments OpenAI, Anthropic, Google, and HuggingFace SDKs on import (17 task types across every modality):

```python
import kalibr  # Must be first import
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(model="gpt-4o", messages=[...])
# Traced automatically — cost, latency, tokens, success all captured
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
| `KALIBR_PROVISIONING_TOKEN` | Enables `kalibr init` credential auto-provisioning | — |
| `KALIBR_AUTO_INSTRUMENT` | Auto-instrument LLM SDKs on import | `true` |
| `KALIBR_INTELLIGENCE_URL` | Intelligence service URL | `https://kalibr-intelligence.fly.dev` |
| `KALIBR_COLLECTOR_URL` | Ingest endpoint | `https://api.kalibr.systems/api/ingest` |
| `KALIBR_CONSOLE_EXPORT` | Print spans to console | `false` |

## Links

- [Docs](https://kalibr.systems/docs) · [Quickstart](https://kalibr.systems/docs/quickstart)
- [Dashboard](https://dashboard.kalibr.systems)
- [Agent context: llms.txt](https://kalibr.systems/llms.txt) · [setup.txt](https://kalibr.systems/setup.txt)
- [AGENTS.md](AGENTS.md)
- [PyPI](https://pypi.org/project/kalibr/)

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
