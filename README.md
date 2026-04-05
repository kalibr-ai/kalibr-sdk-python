# Kalibr Python SDK

The self-healing execution harness for agent pipelines. Every model call gets a task-specific meta prompt, automatic failure detection, an LLM judge that classifies what went wrong, and smart repair — prompt fix or model swap. Pipelines keep running. You don't touch them.

Open source SDK. Hosted routing intelligence.

[![PyPI version](https://img.shields.io/pypi/v/kalibr)](https://pypi.org/project/kalibr/)
[![Python](https://img.shields.io/pypi/pyversions/kalibr)](https://pypi.org/project/kalibr/)
[![License](https://img.shields.io/github/license/kalibr-ai/kalibr-sdk-python)](LICENSE)

## What it does

* **Routes to lower-cost paths automatically** — Simple requests move to cheaper models. Hard requests stay on stronger ones. No rules to write.
* **Adapts as conditions change** — When a model degrades, a tool fails, or pricing shifts, Kalibr moves traffic to a better path automatically.
* **Learns from production** — Uses Thompson Sampling on real outcomes, not static benchmarks. Gets better with every request.
* **No manual retuning** — No config changes, no dashboards to watch, no brittle routing rules.
* **Auto-instrumentation** — Traces OpenAI, Anthropic, Google, and DeepSeek calls with zero code changes.
* **Any model, any modality** — Text, voice, image, embeddings, classification. Any provider, any task type.
* **Full tracing** — See exactly why Kalibr made each routing decision.
* **Framework integrations** — LangChain, CrewAI, OpenAI Agents SDK, LiveKit, Pipecat.

## Quick install — hand this to your coding agent

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

### Cut your OpenClaw token costs after the Anthropic billing change

Anthropic's April 4, 2026 billing change removed OAuth subscription access for OpenClaw. Users on API keys are now paying per-token for everything their agent does.

Most agent workloads are mixed: some tasks need a frontier model, most do not. Routing everything to Sonnet or Opus at API rates when DeepSeek or Llama can handle the same work is the main driver of high bills.

Kalibr classifies each task before it reaches the model and routes it to the cheapest option that passes structural evals for that task type. The routing improves over time as outcomes feed back into the bandit.

**Quickstart with OpenClaw:**

```bash
pip install kalibr
kalibr prompt --openclaw --email you@example.com
# paste the output into your OpenClaw agent
```

**Manual wiring:**

```python
import kalibr  # must be first import
from kalibr_integration.kalibr_pipeline import classify_and_route

output = classify_and_route("Scrape the top 10 results from this search page")
# routes to DeepSeek automatically, 10-50x cheaper than Sonnet for this task type
```

Benchmark: 75% lower model spend vs. routing everything to Sonnet, measured across 500k requests and 12 task types. Free tier at dashboard.kalibr.systems.

## Coding Agent Setup

If you're using Claude Code, Cursor, Windsurf, or any coding agent to build with Kalibr, add the appropriate context file to your project so the agent generates Router-based code by default.

**Claude Code / Codex:**
Copy [templates/CLAUDE.md](templates/CLAUDE.md) to your project root as `CLAUDE.md`

**Cursor / Windsurf:**
Copy [templates/.cursorrules](templates/.cursorrules) to your project root as `.cursorrules`

Once added, your coding agent will automatically:
- Use `Router` instead of raw LLM clients
- Always put `import kalibr` first
- Include outcome reporting in every agent it builds

## Agent Starter Template

Need a production-ready agent scaffold with Kalibr already wired in?

**[kalibr-ai/agent-starter](https://github.com/kalibr-ai/agent-starter)** — clone and ship.

```bash
git clone https://github.com/kalibr-ai/agent-starter.git my-agent
cd my-agent
cp .env.example .env  # fill in your keys
pip install -r requirements.txt
python agent.py
```

Includes Router wired in, CLAUDE.md and .cursorrules for coding agents, and routes between gpt-4o-mini and claude-sonnet out of the box.

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

## DeepSeek

DeepSeek models work out of the box — no separate SDK, no extra config beyond `DEEPSEEK_API_KEY`:

```python
from kalibr import Router

router = Router(
    goal="classify_icp",
    paths=["deepseek-chat", "gpt-4o-mini", "claude-sonnet-4-20250514"],
)
response = router.completion(messages=[{"role": "user", "content": "Is this an ICP fit?"}])
```

Supported models: `deepseek-chat` (V3), `deepseek-reasoner` (R1), `deepseek-coder`. Kalibr attributes costs and spans correctly for each.

---

## Installation

```bash
pip install kalibr

# For accurate token counting
pip install kalibr[tokens]

# For voice AI (ElevenLabs, Deepgram)
pip install kalibr[voice]
```

## Setup

Get your credentials from [dashboard.kalibr.systems/settings](https://dashboard.kalibr.systems/settings), then:

```bash
export KALIBR_API_KEY=your-api-key
export KALIBR_TENANT_ID=your-tenant-id
export OPENAI_API_KEY=sk-...           # OpenAI models
export ANTHROPIC_API_KEY=sk-ant-...    # Anthropic / Claude models
export DEEPSEEK_API_KEY=sk-...         # DeepSeek models (deepseek-chat, deepseek-reasoner)
export HF_API_TOKEN=hf_...             # HuggingFace private models / rate-limit bypass
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

## Self-healing execution loop

Every model call runs through a self-contained healing loop — no orchestrator required:

1. **Meta prompt generation** — Kalibr instruments an LLM (your API key) to generate a task-specific system prompt from your goal and request
2. **Model call** — runs on your API key with the meta prompt as system message
3. **Gate 1 structural eval** — deterministic: did the output match the expected format?
4. **If failure: LLM judge** — instruments another LLM (your API key) to classify the failure:
   - Prompt problem → meta prompt is repaired and retried on the same model
   - Model problem → swap to next-best model and retry
5. **Outcome reported** — bandit updates for (model × prompt variant × goal)

Your original messages are never modified. All LLM calls for meta prompt generation and repair run on your API keys — zero Kalibr inference cost.

### Enable the heal loop

```python
from kalibr import Router

router = Router(goal="summarization", paths=["gpt-4o-mini", "deepseek-chat"])

response = router.completion(
    messages=[{"role": "user", "content": "Summarize this article..."}],
    healing=True,  # Gate 1 eval + prompt repair + model swap on failure
)

print(response.kalibr_healed)      # True if healing fired
print(response.kalibr_heal_count)  # Number of repair attempts
```

### Tuning the heal loop with `HealConfig`

```python
from kalibr import Router, HealConfig

config = HealConfig(
    max_retries=2,             # Repair attempts before model swap
    gate2_enabled=True,        # LLM quality judge (uses DEEPSEEK_API_KEY)
    meta_prompt_enabled=True,  # Generate task-specific system prompt
    judge_model="deepseek-chat",
)

router = Router(goal="summarization", paths=["gpt-4o-mini", "deepseek-chat"])
response = router.completion(
    messages=[{"role": "user", "content": "Summarize this article..."}],
    healing=True,
    heal_config=config,
)
```

## Multi-step pipelines

`router.pipeline()` runs a sequence of goals end-to-end, with healing applied at each step and outputs chained between steps:

```python
from kalibr import Router

router = Router(goal="research", paths=["gpt-4o", "deepseek-chat"])

result = router.pipeline(
    [
        {
            "goal": "research",
            "messages": [{"role": "user", "content": "Research this topic..."}],
        },
        {
            "goal": "outreach_generation",
            "messages": [{"role": "user", "content": "Write email"}],
            "chain": True,  # Feed previous step's output into this step
        },
    ],
    healing=True,
    pipeline_id="my-pipeline",
)

print(result["success"])      # True if all steps succeeded
print(result["total_heals"])  # Total heals across all steps
for step in result["steps"]:
    print(step["goal"], step["healed"], step["model_used"])
```

## Pipeline isolation with `pipeline_id`

Pass a `pipeline_id` to keep routing outcomes from bleeding between unrelated agents that share the same goal:

```python
response = router.completion(
    messages=[...],
    pipeline_id="invoice-processing",  # Isolate routing for this pipeline
)
```

Two agents using the same `goal` but different `pipeline_id`s maintain independent bandit state, so a bad run in one pipeline won't shift traffic in the other.

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
pip install kalibr[voice]           # ElevenLabs + Deepgram voice AI
pip install kalibr[livekit]         # LiveKit Agents
pip install kalibr[pipecat]         # Pipecat pipelines
```

## Voice AI

Route and trace TTS/STT operations with the same outcome-learning loop:

```python
from kalibr import Router

# TTS routing
tts_router = Router(
    goal="narrate_article",
    paths=["tts-1", "eleven_multilingual_v2"],
    success_when=lambda out: out is not None,
)
result = tts_router.synthesize("Hello from Kalibr!", voice="alloy")
# result.audio, result.cost_usd, result.kalibr_trace_id

# STT routing
stt_router = Router(goal="transcribe_call", paths=["whisper-1"])
result = stt_router.transcribe(audio_bytes, audio_duration_seconds=150.0)
# result.text, result.cost_usd, result.kalibr_trace_id
```

Auto-instrument voice SDKs alongside text LLMs:

```python
from kalibr import auto_instrument
auto_instrument(["openai", "elevenlabs", "deepgram"])
# OpenAI TTS/Whisper, ElevenLabs, and Deepgram calls are now traced with cost tracking
```

Voice agent framework instrumentation:

```python
from kalibr_voice import KalibrLiveKitInstrumentor, KalibrPipecatInstrumentor

KalibrLiveKitInstrumentor().instrument()   # Trace LiveKit Agent STT→LLM→TTS pipeline
KalibrPipecatInstrumentor().instrument()   # Trace Pipecat processors
```

## Auto-Instrumentation

Kalibr auto-instruments OpenAI, Anthropic, Google, and HuggingFace SDKs on import (17 task types across every modality):

```python
import kalibr  # Must be first import — patches OpenAI, Anthropic, Google, HuggingFace
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(model="gpt-4o", messages=[...])
# Traced automatically — cost, latency, tokens captured

# DeepSeek works automatically — same OpenAI SDK, detected by model prefix
from openai import OpenAI
deepseek = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
response = deepseek.chat.completions.create(model="deepseek-chat", messages=[...])
# Span labeled deepseek.chat.completions.create, cost at DeepSeek rates
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

## Current Version / Status

- **PyPI version:** `1.14.1` — [pypi.org/project/kalibr](https://pypi.org/project/kalibr/)
- **Python:** 3.10, 3.11, 3.12
- **Status:** Production. Used in live agent pipelines.
- **Latest changes (1.14.x):** Full heal loop (`healing=True`), `HealConfig` tuning, `router.pipeline()` multi-step execution, `pipeline_id` isolation, Gate 2 LLM judge, LLM meta-prompt generation
- **TS SDK counterpart:** `@kalibr/sdk` v1.14.1 — see [kalibr-sdk-ts](https://github.com/kalibr-ai/kalibr-sdk-ts)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0
