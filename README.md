# Kalibr Python SDK

Kalibr routes LLM calls to the cheapest model that passes quality evals for your task type. Fails heal automatically.

[![PyPI version](https://img.shields.io/pypi/v/kalibr)](https://pypi.org/project/kalibr/)
[![Python](https://img.shields.io/pypi/pyversions/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/github/license/kalibr-ai/kalibr-sdk-python)](LICENSE)

Version: **1.14.1** · Python 3.10, 3.11, 3.12

## Install

```bash
pip install kalibr
```

Set credentials from [dashboard.kalibr.systems/settings](https://dashboard.kalibr.systems/settings):

```bash
export KALIBR_API_KEY=sk_...
export KALIBR_TENANT_ID=tenant_...
export OPENAI_API_KEY=sk-...
export DEEPSEEK_API_KEY=sk-...
```

## Quickstart

```python
from kalibr import Router

router = Router(goal="summarization", paths=["gpt-4o-mini", "deepseek-chat"])
response = router.completion(messages=[{"role": "user", "content": "Summarize the SEC's 2024 climate disclosure rule."}])
print(response.choices[0].message.content)
```

The response shape matches the OpenAI Chat Completions API. Provider keys are yours; Kalibr never holds them.

## How it works

1. **Classify**: Router maps your `goal` to one of 12 task types (see table below).
2. **Greedy routing**: picks the path with the highest historical success rate for that task type, with exploration via Thompson Sampling.
3. **Gate 1 (structural eval)**: deterministic checks for format, length, and output completeness. Runs on every call. No extra LLM cost.
4. **Gate 2 (LLM judge, optional)**: a quality judge (default `deepseek-chat`) scores the output against the goal. Enable with `HealConfig(gate2_enabled=True)`.
5. **Repair on failure**: if a gate fails, Kalibr generates a corrective system prompt and retries on the same model. If the model itself is the problem, Kalibr swaps to the next-best path.
6. **Outcome reporting**: every call writes back to the bandit. The router gets better with every request, without manual tuning.

All meta-prompt generation and judging calls run on your provider keys. Kalibr does not run inference.

## Goal types

| goal_id              | Example task                                         | Default model     |
|----------------------|------------------------------------------------------|-------------------|
| `summarization`      | Condense an article or transcript                    | `gpt-4o-mini`     |
| `classification`     | ICP fit, intent label, sentiment                     | `deepseek-chat`   |
| `extraction`         | Pull company, email, amount, date from text          | `gpt-4o-mini`     |
| `outreach_generation`| Cold email, subject + body                           | `claude-sonnet-4` |
| `code_generation`    | Generate or modify a code snippet                    | `claude-sonnet-4` |
| `research`           | Multi-source research with web search                | `gpt-4o`          |
| `qa`                 | Question answering over context                      | `gpt-4o-mini`     |
| `translation`        | Translate between languages                          | `gpt-4o-mini`     |
| `conversational`     | Multi-turn chat, support, assistant                  | `claude-sonnet-4` |
| `book_meeting`       | Calendar negotiation with tool calls                 | `gpt-4o`          |
| `transcription`      | Speech to text (Whisper, Seamless)                   | `whisper-1`       |
| `narration`          | Text to speech (TTS-1, ElevenLabs)                   | `tts-1`           |

Defaults are starting points. Pass any combination of models in `paths=[...]` and the bandit learns your actual distribution.

## Self-healing

```python
from kalibr import Router, HealConfig

router = Router(goal="summarization", paths=["gpt-4o-mini", "deepseek-chat"])

response = router.completion(
    messages=[{"role": "user", "content": "Summarize this earnings call transcript..."}],
    healing=True,
)

print(response.kalibr_healed)      # True if the heal loop fired
print(response.kalibr_heal_count)  # Number of repair attempts
```

Tune the loop with `HealConfig`:

```python
from kalibr import Router, HealConfig

config = HealConfig(
    max_retries=2,
    gate2_enabled=True,         # LLM quality judge
    meta_prompt_enabled=True,   # Generate task-specific system prompt before the first call
    judge_model="deepseek-chat",
)

router = Router(goal="summarization", paths=["gpt-4o-mini", "deepseek-chat"])
response = router.completion(
    messages=[{"role": "user", "content": "Summarize this earnings call transcript..."}],
    healing=True,
    heal_config=config,
)
```

Your original `messages` are never mutated. Repair prompts are injected as system messages on the retry only.

## Multi-step pipelines

`router.pipeline()` runs a sequence of goals end to end. Healing applies at each step. Set `chain=True` to feed the previous step's output into the next.

```python
from kalibr import Router

router = Router(goal="research", paths=["gpt-4o", "deepseek-chat"])

result = router.pipeline(
    [
        {
            "goal": "research",
            "messages": [{"role": "user", "content": "Research Acme Corp's pricing model."}],
        },
        {
            "goal": "outreach_generation",
            "messages": [{"role": "user", "content": "Write a cold email referencing the research."}],
            "chain": True,
        },
    ],
    healing=True,
    pipeline_id="acme-outreach",
)

print(result["success"], result["total_heals"])
for step in result["steps"]:
    print(step["goal"], step["model_used"], step["healed"])
```

## pipeline_id

`pipeline_id` isolates routing outcomes between agents that share the same goal. Two agents writing `outreach_generation` for different customer segments will keep independent bandit state, so a bad run in one will not shift traffic in the other.

```python
response = router.completion(
    messages=[...],
    pipeline_id="invoice-processing",
)
```

Use it whenever the same goal is invoked from meaningfully different contexts (different tenants, products, or LLM agents).

## Agent onboarding

If you are integrating Kalibr into a coding agent (Claude Code, Cursor, Windsurf, or any agent that writes code for you), run:

```bash
kalibr prompt
```

This copies a full integration prompt to your clipboard. Pasting it into the agent instructs it to:

1. `pip install kalibr`
2. Run `kalibr auth` and link credentials via device code
3. Scan the codebase, wrap bare LLM client calls with `Router`, and ensure `import kalibr` is the first import
4. Pick sensible `goal` names and 2+ models per `paths=[...]`
5. Add outcome reporting (either `success_when=` or `router.report()`)
6. Run `kalibr verify` to confirm connectivity

The resulting agent calls Router on every task, routes to the cheapest path that succeeds, and reports outcomes back to Kalibr.

## Dashboard

[dashboard.kalibr.systems](https://dashboard.kalibr.systems) is where production routing becomes legible:

- **Goals view**: health status, request volume, success rate, and cost per goal
- **Paths view**: per-model success rate, latency, and cost; which models the bandit is favoring and why
- **Heals view**: when the loop fired, what gate failed, which repair worked, which models needed a swap
- **Failure modes**: breakdown by category (timeout, malformed output, hallucination, rate limit, etc.)
- **Pipelines**: drill into multi-step runs by `pipeline_id`, see per-step heals and model swaps
- **Traces**: every call with its full decision history, gates, repair attempts, and final outcome

## Links

- [Docs](https://kalibr.systems/docs) · [Dashboard](https://dashboard.kalibr.systems)
- [PyPI](https://pypi.org/project/kalibr/) · [TypeScript SDK](https://github.com/kalibr-ai/kalibr-sdk-ts)
- [CHANGELOG](CHANGELOG.md) · [CONTRIBUTING](CONTRIBUTING.md)

## License

Apache-2.0
