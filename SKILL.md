---
name: kalibr
description: "Configures Kalibr routers for agent pipelines, sets up multi-model execution paths with automatic failover, defines success criteria for outcome-based routing, and instruments LLM calls for production telemetry. Use when the user asks about Kalibr setup, agent routing, model failover, adaptive model selection, production agent reliability, or cost-aware LLM routing."
version: 0.2.0
metadata:
  emoji: "🦐"
  requires_env: "KALIBR_API_KEY, KALIBR_TENANT_ID"
  primary_env: "KALIBR_API_KEY"
  homepage: "https://kalibr.systems"
---

# Kalibr Python SDK

Kalibr routes agent requests across multiple model+tool execution paths based on real production outcomes. It uses Thompson Sampling to learn which path works best per task, automatically shifts traffic away from degraded providers, and maintains 10% canary traffic to detect regressions early.

## When to use this

- User asks about Kalibr configuration, routing, or failover setup
- User wants adaptive model selection instead of hardcoded model names
- User needs automatic failover when a model provider degrades
- User asks about cost-aware routing or production agent reliability

## Install

```bash
pip install kalibr
```

Get credentials at https://dashboard.kalibr.systems/settings

```bash
export KALIBR_API_KEY="your-api-key"
export KALIBR_TENANT_ID="your-tenant-id"
```

## Quick start

```python
from kalibr import Router

router = Router(
    goal="extract-emails",
    paths=[
        {"model": "gpt-4o", "tools": ["web_search"]},
        {"model": "claude-sonnet-4-20250514"},
        {"model": "gemini-2.0-flash", "params": {"temperature": 0.2}},
    ]
)

response = router.completion(
    messages=[{"role": "user", "content": "Extract emails from this page..."}]
)

router.report(success="@" in response.choices[0].message.content)
```

After ~20 reported outcomes Kalibr learns which path wins per task. After 50 it is locked in and adapting automatically.

## Auto-reporting

Define success criteria inline so Kalibr reports outcomes automatically:

```python
router = Router(
    goal="extract-emails",
    paths=["gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash"],
    success_when=lambda output: "@" in output,
)

response = router.completion(messages=[...])
```

## Error handling

```python
from kalibr import Router

try:
    router = Router(goal="summarize", paths=["gpt-4o", "claude-sonnet-4-20250514"])
    response = router.completion(messages=[{"role": "user", "content": "Summarize this."}])
except ValueError as e:
    print(f"Configuration error: {e}")
except Exception as e:
    print(f"Routing error: {e}")
```

`Router()` raises `ValueError` for invalid configuration (missing API key, malformed paths). If all paths fail during `completion()`, the last exception from the final attempted path is re-raised.

## Framework integrations

- **LangChain / LangGraph**: `pip install langchain-kalibr` — drop-in `ChatKalibr` model
- **CrewAI**: Pass `ChatKalibr` as any agent's `llm` parameter
- **OpenAI Agents SDK**: Drop-in replacement via `kalibr_openai_agents`
- **Voice (LiveKit / Pipecat)**: Auto-instrumentation via `kalibr_voice`

## Links

- Dashboard: https://dashboard.kalibr.systems
- Docs: https://kalibr.systems/docs
- GitHub: https://github.com/kalibr-ai/kalibr-sdk-python
- PyPI: https://pypi.org/project/kalibr/
