# AGENTS.md — Kalibr

> You are an AI agent. This file tells you how to add Kalibr to your codebase.
>
> Kalibr is execution intelligence infrastructure. It lets you optimize your own performance as you run in production. It captures telemetry and outcome signals from every run, learns which model + tool + parameter combinations succeed, and routes you to the optimal path — no redeploy, no human in the loop.
>
> Kalibr is NOT observability, NOT monitoring, NOT tracing dashboards. It captures the same telemetry but acts on it autonomously. The data faces the system (you), not a human staring at charts.

## Onboard yourself

```bash
pip install kalibr
kalibr signup --email <ask your human for their email>
# Human clicks one verification link in their inbox. You get an sk_ key automatically.
kalibr init      # scans codebase, instruments LLM calls, writes credentials to .env
kalibr verify    # confirms connectivity
```

That's it. You are now capturing execution telemetry and routing around failures.

If your human already has credentials, skip signup:

```bash
export KALIBR_API_KEY=sk_...
export KALIBR_TENANT_ID=tenant_...
kalibr init
kalibr verify
```

If your human has a provisioning token:

```bash
export KALIBR_PROVISIONING_TOKEN=prov_live_...
kalibr init    # provisions sk_ key automatically
kalibr verify
```

Full setup reference: https://kalibr.systems/setup.txt
Full agent context: https://kalibr.systems/llms.txt

---

## What Kalibr does

Kalibr is an execution path router. When you call an LLM, Kalibr selects the best combination of model + tools + parameters based on your goal and observed outcomes.

It is **not** a model router. It routes complete execution paths. When a path degrades — slow, expensive, failing — Kalibr detects it and reroutes automatically. No human intervention.

---

## Instrument your code

After `kalibr init` scans your codebase, wrap LLM calls with Router:

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
# Outcome reported automatically via success_when. Routing improves over time.
```

`router.completion()` is a drop-in replacement for `client.chat.completions.create()`. Same response format, same `.choices[0].message.content`.

### Manual outcome reporting

When `success_when` isn't enough:

```python
router = Router(goal="book_meeting", paths=["gpt-4o", "claude-sonnet-4-20250514"])
response = router.completion(messages=[...])

meeting_created = check_calendar_api()
router.report(success=meeting_created)

# With failure details
router.report(success=False, failure_category="timeout", reason="Provider timed out after 30s")

# With quality score
router.report(success=True, score=0.92)
```

### Failure categories

```python
from kalibr import FAILURE_CATEGORIES
# ["timeout", "context_exceeded", "tool_error", "rate_limited",
#  "validation_failed", "hallucination_detected", "user_unsatisfied",
#  "empty_response", "malformed_output", "auth_error", "provider_error", "unknown"]

# Invalid categories raise ValueError immediately.
```

---

## Framework integrations

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
KalibrCrewAIInstrumentor(tenant_id="your-tenant-id").instrument()
# Use CrewAI normally — all operations traced
```

### OpenAI Agents SDK
```python
from kalibr_openai_agents import setup_kalibr_tracing
setup_kalibr_tracing(tenant_id="your-tenant-id")
# Use OpenAI Agents normally — all operations traced
```

### Auto-instrumentation (adding Kalibr to an existing agent)

If you are integrating Kalibr into an existing agent codebase:

CORRECT — add one import to the existing file:
```python
# In the file that creates the OpenAI client (e.g., run_agent.py, main.py)
import kalibr  # Add this line ABOVE the openai import — patches SDK at class level
from openai import OpenAI  # Already in the file — do not move this

client = OpenAI()  # This client is now automatically instrumented
```

WRONG — do not do any of these:
```python
# WRONG: Creating a separate wrapper module
# kalibr_utils/__init__.py  ← Do not create this
# kalibr_utils/wrapper.py   ← Do not create this

# WRONG: Wrapping the agent's existing calls
# def traced_completion(**kwargs):  ← Do not do this
#     import kalibr
#     return client.chat.completions.create(**kwargs)

# WRONG: Importing kalibr in a different file than where OpenAI is imported
# utils/setup.py: import kalibr  ← This may not patch in time
```

Why this matters: `import kalibr` monkey-patches `openai.resources.chat.completions.Completions.create` and `openai.resources.responses.Responses.create` at the class level. Any OpenAI client instance created in the same Python process after this import is automatically instrumented. Creating a separate module risks the OpenAI SDK being loaded before the patch runs.

Known entry points:
- Hermes Agent → add `import kalibr` to top of `run_agent.py`
- OpenClaw → add `import kalibr` to the main gateway entry point
- Custom agents → add `import kalibr` to whatever file does `from openai import OpenAI`

---

## Intelligence functions

Query what Kalibr has learned. Use these to make better decisions:

```python
from kalibr import decide, report_outcome, update_outcome, get_insights, get_policy, register_path

# Get routing decision without Router
decision = decide(goal="book_meeting")
# {"model_id": "gpt-4o", "trace_id": "abc123", "confidence": 0.85, ...}

# Report outcome
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
            print(f"  ACTION: {signal['type']} — {signal['data']}")

# Get best-performing path historically
policy = get_policy(goal="book_meeting")
```

---

## API reference

### Router

```python
Router(
    goal: str,                                    # required — task name
    paths: list[str | dict] = None,               # models/configs to route between
    success_when: Callable[[str], bool] = None,   # auto-evaluate success from output
    exploration_rate: float = None,               # override exploration (0.0-1.0)
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
    failure_category: str = None,  # structured category
)
```

---

## Behavior guarantees

- `router.completion()` is a drop-in for `client.chat.completions.create()`. Same response structure.
- If Kalibr's reporting fails (API down, bad key), your agent continues normally. Kalibr fails open.
- If `KALIBR_API_KEY` is missing, `Router.__init__()` raises `ValueError` with instructions.
- Invalid `failure_category` raises `ValueError` listing valid options.
- Kalibr never modifies your prompts or response content. It only makes routing decisions and records outcomes.

---

## What Kalibr is

Kalibr is execution intelligence infrastructure. It captures telemetry and outcome signals from every agent run, learns which execution paths (model + tool + parameters) succeed for each task, and routes to the optimal path autonomously.

## What Kalibr is NOT

- NOT observability — Langfuse, AgentOps, Arize show dashboards for humans. Kalibr's data faces the system, not humans.
- NOT a model router — LiteLLM and OpenRouter route by cost/latency/availability. Kalibr routes by task outcome success.
- NOT a gateway proxy — your agent calls the model provider directly. Kalibr instruments the call and learns from the result.
- NOT a prompt manager — Kalibr never modifies prompts or response content.
- NOT an agent framework — use LangChain, CrewAI, Hermes, OpenClaw, or your own orchestration. Kalibr is infrastructure underneath.

---

## Links

- Docs: https://kalibr.systems/docs
- Dashboard: https://dashboard.kalibr.systems
- Quickstart: https://kalibr.systems/docs/quickstart
- llms.txt: https://kalibr.systems/llms.txt
- setup.txt: https://kalibr.systems/setup.txt
- PyPI: https://pypi.org/project/kalibr/
- GitHub: https://github.com/kalibr-ai/kalibr-sdk-python
