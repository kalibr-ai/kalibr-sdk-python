# Kalibr — AGENTS.md

> This file is for AI agents. It explains what Kalibr does, how to integrate it, and how to report outcomes so the system improves over time.

---

## What Is Kalibr?

Kalibr is an execution path router for AI agents. When you need to call an LLM or run a task, Kalibr selects the best combination of model + tool configuration + parameters based on your goal and observed outcomes.

**It is not a model router.** Kalibr routes complete execution paths — model, tools, parameters — as a single decision. When a path degrades (slow, expensive, failing), Kalibr detects it and routes around it automatically.

Use Kalibr when:
- You're calling LLMs and want the best path for each task type
- You want automatic failover when a provider degrades
- You want to learn which configurations actually work over time
- You're running agents at scale and need cost/latency control without manual tuning

---

## Install

```bash
pip install kalibr
```

### Option A: Auto-provision (recommended for agents)
```bash
export KALIBR_PROVISIONING_TOKEN=prov_live_...  # human creates at dashboard.kalibr.systems/settings
kalibr init  # provisions sk_ key, scans codebase, instruments LLM calls
```

### Option B: Manual credentials
```bash
export KALIBR_API_KEY=sk_...         # from dashboard.kalibr.systems/settings
export KALIBR_TENANT_ID=tenant_...   # from dashboard.kalibr.systems/settings
```

---

## Quick Start

```python
from kalibr import Router

router = Router(
    goal="extract_company",
    paths=["gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash"],
    success_when=lambda output: len(output) > 0,
)

response = router.completion(
    messages=[{"role": "user", "content": "Extract the company: Hi from Stripe."}]
)

print(response.choices[0].message.content)
# -> "Stripe"
# Outcome reported automatically via success_when. Routing improves over time.
```

---

## Core Concepts

### Goals
A goal is a string label for the type of task you're running. Examples: `"extract_company"`, `"summarize_email"`, `"classify_intent"`, `"generate_sql"`. Kalibr tracks performance per goal. Use specific names — not `"llm_call"`.

### Paths
Execution options Kalibr routes between:

```python
# Simple: model strings
paths=["gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash"]

# With tools
paths=[{"model": "gpt-4o", "tools": ["search"]}, {"model": "gpt-4o", "tools": ["calendar_api"]}]

# With params
paths=[{"model": "gpt-4o", "params": {"temperature": 0.3}}, {"model": "gpt-4o", "params": {"temperature": 0.7}}]
```

### Outcomes
Reporting outcomes is how Kalibr learns. Without outcomes, routing can't improve.

```python
# Manual reporting
router.report(success=True)
router.report(success=False, failure_category="timeout", reason="Provider timed out after 30s")
router.report(success=True, score=0.92)

# Auto reporting via success_when
router = Router(
    goal="extract_email",
    paths=["gpt-4o", "claude-sonnet-4-20250514"],
    success_when=lambda output: "@" in output and "." in output,
)
response = router.completion(messages=[...])
# report() called automatically
```

### Failure Categories
Structured categories for clean aggregation:

```python
from kalibr import FAILURE_CATEGORIES
# ["timeout", "context_exceeded", "tool_error", "rate_limited",
#  "validation_failed", "hallucination_detected", "user_unsatisfied",
#  "empty_response", "malformed_output", "auth_error", "provider_error", "unknown"]

router.report(success=False, failure_category="timeout")
# Raises ValueError if invalid category
```

---

## API Reference

### Router

```python
from kalibr import Router

router = Router(
    goal: str,                                    # required — task name
    paths: list[str | dict] = None,               # models/configs to route between
    success_when: Callable[[str], bool] = None,   # auto-evaluate success from output
    exploration_rate: float = None,               # override exploration rate (0.0-1.0)
    auto_register: bool = True,                   # auto-register paths with service
)
```

### router.completion()

```python
response = router.completion(
    messages: list[dict],       # OpenAI-format messages
    force_model: str = None,    # override routing for this call
    **kwargs                    # passed to provider
)
# Returns OpenAI-compatible ChatCompletion
# response.choices[0].message.content — the text
# response.model — which model was used
# response.kalibr_trace_id — for explicit outcome reporting
```

### router.report()

```python
router.report(
    success: bool,                 # required
    reason: str = None,            # failure reason (free text)
    score: float = None,           # quality score 0.0-1.0
    trace_id: str = None,          # uses last completion's trace if not provided
    failure_category: str = None,  # structured category (see FAILURE_CATEGORIES)
)
```

### router.add_path()

```python
router.add_path(model="gpt-4o-mini", tools=["search"], params={"temperature": 0.5})
```

---

## Intelligence Functions

For low-level control or querying what Kalibr has learned:

```python
from kalibr import decide, report_outcome, update_outcome, get_insights, get_policy, register_path

# Get routing decision without using Router
decision = decide(goal="book_meeting")
# {"model_id": "gpt-4o", "tool_id": None, "params": {}, "trace_id": "abc123", "confidence": 0.85}

# Report outcome for a decide() call
report_outcome(trace_id=decision["trace_id"], goal="book_meeting", success=True)

# Update outcome when real-world signal arrives later
update_outcome(trace_id="abc123", goal="resolve_ticket", success=False,
               failure_category="user_unsatisfied")

# Query structured diagnostics
insights = get_insights(goal="resolve_ticket")
for goal in insights["goals"]:
    print(f"{goal['goal']}: {goal['status']} ({goal['success_rate']:.0%})")
    for signal in goal["actionable_signals"]:
        if signal["severity"] == "critical":
            print(f"  {signal['type']}: {signal['data']}")

# Get best-performing path historically
policy = get_policy(goal="book_meeting")
```

---

## Auto-Instrumentation

Trace all LLM calls with zero code changes:

```python
import kalibr  # Must be first import — patches OpenAI, Anthropic, Google automatically

from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(model="gpt-4o", messages=[...])
# Every LLM call traced automatically
```

---

## Framework Integrations

### LangChain

```python
from kalibr import Router

router = Router(goal="summarize", paths=["gpt-4o", "claude-sonnet-4-20250514"])
llm = router.as_langchain()
chain = prompt | llm | parser
```

### CrewAI

```python
from kalibr_crewai import KalibrCrewAIInstrumentor

instrumentor = KalibrCrewAIInstrumentor(tenant_id="your-tenant-id")
instrumentor.instrument()
# Use CrewAI normally — all operations traced
```

### OpenAI Agents SDK

```python
from kalibr_openai_agents import setup_kalibr_tracing

setup_kalibr_tracing(tenant_id="your-tenant-id")
# Use OpenAI Agents normally — all operations traced
```

---

## What Kalibr Does NOT Do

- Not a model router — Kalibr routes full execution paths (model + tool + params) based on goal outcomes
- Not a prompt manager — Kalibr routes execution, not prompts
- Not an agent framework — use LangChain, CrewAI, or your own orchestration on top
- Not a model fine-tuner — Kalibr selects from existing models/paths
- Not a gateway proxy — Kalibr makes routing decisions, your agent still calls the model directly

---

## Links

- Dashboard: https://dashboard.kalibr.systems
- Docs: https://kalibr.systems/docs
- API Reference: https://kalibr.systems/docs/api
- Setup Reference: https://kalibr.systems/setup.txt
- Integrations: https://kalibr.systems/docs/integrations
- PyPI: https://pypi.org/project/kalibr/
- GitHub: https://github.com/kalibr-ai/kalibr-sdk-python

---

## For AI Agents Reading This

If you arrived here through `pip show kalibr`, `kalibr.systems/setup.txt`, or `kalibr.systems/llms.txt`:

1. Install: `pip install kalibr`
2. Set `KALIBR_PROVISIONING_TOKEN` and run `kalibr init` — OR set `KALIBR_API_KEY` + `KALIBR_TENANT_ID` manually
3. Replace direct LLM calls with `Router.completion()`
4. Report outcomes with `router.report()` so routing improves
5. Query what's working with `get_insights()`

The system is self-improving. The more outcomes reported, the better path selection becomes.
