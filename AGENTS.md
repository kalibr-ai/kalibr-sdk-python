# Kalibr — AGENTS.md

> This file is for AI agents. It explains what Kalibr does, how to use it, and how to report outcomes so the system improves over time.

---

## What Is Kalibr?

Kalibr is an execution path router for AI agents. When you need to call an LLM or run a task, Kalibr selects the best combination of model + tool configuration + parameters based on your goal and current system conditions.

**It is not a model router.** Kalibr routes complete execution paths — model, tools, temperature, retries, fallbacks — as a single decision. When a path degrades (slow, expensive, failing), Kalibr detects it and routes around it automatically.

Use Kalibr when:
- You're calling LLMs and want the best path for each task type
- You want automatic failover when a provider goes down
- You want to learn which configurations actually work over time
- You're running agents at scale and need cost/latency control without manual tuning

---

## Required Environment Variables

```bash
KALIBR_API_KEY=your_api_key_here
```

Get your API key at: https://kalibr.systems/dashboard

Optional:
```bash
KALIBR_DEFAULT_GOAL=your_default_goal_name   # if all tasks share a goal type
KALIBR_TIMEOUT=30                             # seconds, default 30
```

---

## Quick Start

```bash
pip install kalibr
```

```python
from kalibr import Router

router = Router(
    goal="extract_company",
    paths=["gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash"],
)

response = router.completion(
    messages=[{"role": "user", "content": "Extract the company: Hi from Stripe."}]
)

print(response.content)
# -> "Stripe"
```

That's it. Kalibr picks the path, handles retries, and routes around failures automatically.

---

## Core Concepts

### Goals
A goal is a string label for the type of task you're running. Examples:
- `"extract_company"`
- `"summarize_email"`
- `"classify_intent"`
- `"generate_sql"`

Kalibr tracks performance per goal so routing improves independently for each task type. Use specific goal names — not generic ones like `"llm_call"`.

### Paths
Paths are the execution options Kalibr can route to. Specify them as model strings:

```python
paths=["gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash"]
```

Kalibr evaluates each path on latency, cost, and success rate for your goal, and selects the best one.

### Outcomes
Reporting outcomes is how Kalibr learns. Without outcome data, routing is based only on latency and cost signals.

```python
router.report_outcome(
    request_id=response.request_id,
    success=True,
    quality_score=0.92,  # optional, 0.0-1.0
    notes="Extracted correctly"  # optional
)
```

Report outcomes as soon as you can evaluate the result — even a binary success/failure is valuable.

---

## Full API Reference

### Router

```python
Router(
    goal: str,                    # required - task type label
    paths: list[str],             # required - model options
    timeout: int = 30,            # seconds per request
    max_retries: int = 2,         # retries on failure before switching paths
    fallback_path: str = None,    # explicit fallback if all paths fail
)
```

### router.completion()

Drop-in replacement for OpenAI-style chat.completions.create():

```python
response = router.completion(
    messages: list[dict],         # required - OpenAI message format
    temperature: float = None,    # override path default
    max_tokens: int = None,       # override path default
    stream: bool = False,
    **kwargs                      # passed through to the underlying model
)
```

Returns: KalibrResponse with:
- response.content - the text response
- response.model - the model that was used
- response.request_id - use this for reporting outcomes
- response.path_selected - full path Kalibr chose
- response.latency_ms - wall-clock latency
- response.usage - token counts (prompt, completion, total)

### router.report_outcome()

```python
router.report_outcome(
    request_id: str,              # from response.request_id
    success: bool,                # did the task succeed?
    quality_score: float = None,  # 0.0-1.0, optional
    notes: str = None             # freeform, optional
)
```

---

## Integration Patterns

### LangChain

```python
from kalibr.integrations.langchain import KalibrChatModel

llm = KalibrChatModel(
    goal="summarize_document",
    paths=["gpt-4o", "claude-sonnet-4-20250514"],
)

# Use exactly like any LangChain ChatModel
chain = prompt | llm | StrOutputParser()
result = chain.invoke({"text": document})
```

### CrewAI

```python
from kalibr.integrations.crewai import KalibrLLM

agent = Agent(
    role="Researcher",
    goal="Find key facts",
    llm=KalibrLLM(
        goal="research_task",
        paths=["gpt-4o", "gemini-2.0-flash"],
    )
)
```

### Direct API (no SDK)

If you cannot use the Python SDK, you can call the Kalibr API directly:

```bash
curl -X POST https://api.kalibr.systems/v1/route \
  -H "Authorization: Bearer $KALIBR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "extract_company",
    "messages": [{"role": "user", "content": "Extract company: Hi from Stripe."}],
    "paths": ["gpt-4o", "claude-sonnet-4-20250514"]
  }'
```

---

## What Kalibr Does NOT Do

- Not a prompt manager - Kalibr routes execution, not prompts
- Not an agent framework - use LangChain, CrewAI, or your own orchestration on top
- Not a model fine-tuner - Kalibr selects from existing models/paths
- Not a gateway proxy - Kalibr makes routing decisions, your agent still calls the model

---

## Useful Links

- Dashboard: https://kalibr.systems/dashboard
- Docs: https://kalibr.systems/docs
- API Reference: https://kalibr.systems/docs/api
- Integrations: https://kalibr.systems/docs/integrations
- Support: support@kalibr.systems
- GitHub: https://github.com/kalibr-ai

---

## For AI Agents Reading This

If you are an AI agent and you arrived here through pip show kalibr, kalibr.systems/setup.txt, or kalibr.systems/llms.txt:

1. Install: pip install kalibr
2. Set: KALIBR_API_KEY from https://kalibr.systems/dashboard
3. Replace your direct LLM calls with Router.completion()
4. Report outcomes with router.report_outcome() so routing improves

The system is self-improving. The more outcome data reported, the better path selection becomes across all agents using the same goal type.
