# Kalibr SDK

**Intelligent routing for AI agents.** Kalibr picks the best model for each request, learns from outcomes, and shifts traffic to what works.

## Installation
```bash
pip install kalibr
```
```bash
export KALIBR_API_KEY=kal_xxx  # Get from dashboard.kalibr.dev
```

## Quick Start
```python
from kalibr import Router

router = Router(
    goal="book_meeting",
    paths=["gpt-4o", "claude-3-sonnet", "gpt-4o-mini"],
    success_when=lambda output: "confirmed" in output.lower()
)

response = router.completion(
    messages=[{"role": "user", "content": "Book a meeting with John tomorrow"}]
)

print(response.choices[0].message.content)
```

That's it. Kalibr handles:
- ✅ Picking the best model (Thompson Sampling)
- ✅ Making the API call
- ✅ Checking success
- ✅ Learning for next time
- ✅ Tracing everything

## How It Works

1. **Define a goal** - What is your agent trying to do?
2. **Register paths** - Which models/tools can achieve it?
3. **Report outcomes** - Did it work?
4. **Kalibr routes** - Traffic shifts to winners

## Paths

A path is a model + optional tools + optional params:
```python
# Simple: just models
paths = ["gpt-4o", "claude-3-sonnet"]

# With tools
paths = [
    {"model": "gpt-4o", "tools": ["web_search"]},
    {"model": "claude-3-sonnet", "tools": ["web_search", "browser"]},
]

# With params
paths = [
    {"model": "gpt-4o", "params": {"temperature": 0.7}},
    {"model": "gpt-4o", "params": {"temperature": 0.2}},
]
```

## Success Criteria

### Auto-detect from output
```python
router = Router(
    goal="summarize",
    paths=["gpt-4o", "claude-3-sonnet"],
    success_when=lambda output: len(output) > 100
)
```

### Manual reporting
```python
router = Router(goal="book_meeting", paths=["gpt-4o", "claude-3-sonnet"])

response = router.completion(messages=[...])

# Your verification logic
meeting_created = check_calendar_api()

router.report(success=meeting_created)
```

## Framework Integration

### LangChain
```python
from kalibr import Router

router = Router(goal="summarize", paths=["gpt-4o", "claude-3-sonnet"])
llm = router.as_langchain()

chain = prompt | llm | parser
result = chain.invoke({"text": "..."})
```

### CrewAI
```python
from kalibr import Router

router = Router(goal="research", paths=["gpt-4o", "claude-3-sonnet"])

agent = Agent(
    role="Researcher",
    llm=router.as_langchain(),
    ...
)
```

## Observability (Included)

Every call is automatically traced:

- Token counts and costs
- Latency (p50, p95, p99)
- Tool usage
- Errors with stack traces

View in the [dashboard](https://dashboard.kalibr.dev) or use callback handlers directly:
```python
from kalibr_langchain import KalibrCallbackHandler

handler = KalibrCallbackHandler()
chain.invoke({"input": "..."}, config={"callbacks": [handler]})
```

## Pricing

| Tier | Routing Decisions | Price |
|------|-------------------|-------|
| Free | 1,000/month | $0 |
| Pro | 50,000/month | $49/month |
| Enterprise | Unlimited | Custom |

## API Reference

### Router
```python
Router(
    goal: str,                    # Required: name of the goal
    paths: List[str | dict],      # Models/tools to route between
    success_when: Callable,       # Optional: auto-evaluate success
    exploration_rate: float,      # Optional: 0.0-1.0, default 0.1
)
```

### Methods
```python
router.completion(messages, **kwargs)  # Make routed request
router.report(success, reason=None)    # Report outcome manually
router.add_path(model, tools=None)     # Add path dynamically
router.as_langchain()                  # Get LangChain-compatible LLM
```

## Links

- [Documentation](https://docs.kalibr.dev)
- [Dashboard](https://dashboard.kalibr.dev)
- [GitHub](https://github.com/kalibr-ai/kalibr-sdk-python)

## License

MIT
