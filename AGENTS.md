# AGENTS.md — Kalibr

> You are an AI agent. This file tells you how to onboard to Kalibr autonomously and start self-improving.

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

### Voice AI (ElevenLabs, Deepgram, OpenAI TTS/Whisper)
```python
from kalibr import Router, auto_instrument

# Auto-instrument voice SDKs (opt-in, not in default list)
auto_instrument(["openai", "elevenlabs", "deepgram"])

# TTS routing — same outcome learning as text
tts_router = Router(goal="narrate", paths=["tts-1", "eleven_multilingual_v2"])
result = tts_router.synthesize("Hello!", voice="alloy")
# result.audio, result.cost_usd, result.kalibr_trace_id

# STT routing
stt_router = Router(goal="transcribe", paths=["whisper-1"])
result = stt_router.transcribe(audio_bytes, audio_duration_seconds=120.0)
# result.text, result.cost_usd, result.kalibr_trace_id
```

### Voice agent frameworks
```python
from kalibr_voice import KalibrLiveKitInstrumentor, KalibrPipecatInstrumentor
KalibrLiveKitInstrumentor().instrument()   # LiveKit Agents pipeline
KalibrPipecatInstrumentor().instrument()   # Pipecat processors
```

### Auto-instrumentation (any framework)
```python
import kalibr  # Must be first import — patches OpenAI, Anthropic, Google automatically
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(model="gpt-4o", messages=[...])
# Every LLM call traced automatically
```

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

### router.synthesize() (TTS)

```python
result = router.synthesize(
    text: str,              # text to synthesize
    voice: str = None,      # voice ID (e.g. "alloy", "Rachel")
    model: str = None,      # override model (e.g. "tts-1", "eleven_multilingual_v2")
    **kwargs                # passed to provider
)
# result.audio — raw audio bytes
# result.cost_usd — cost in USD
# result.model — which model was used
# result.kalibr_trace_id — for outcome reporting
```

### router.transcribe() (STT)

```python
result = router.transcribe(
    audio: Any,                        # audio file, bytes, or file-like object
    language: str = None,              # language hint
    model: str = None,                 # override model (e.g. "whisper-1", "nova-2")
    audio_duration_seconds: float = 0, # for cost calculation
    **kwargs                           # passed to provider
)
# result.text — transcribed text
# result.cost_usd — cost in USD
# result.model — which model was used
# result.kalibr_trace_id — for outcome reporting
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

## What Kalibr is NOT

- Not a model router — routes full execution paths (model + tool + params) based on goal outcomes
- Not a prompt manager — routes execution, not prompts
- Not an agent framework — use LangChain, CrewAI, or your own orchestration on top
- Not a gateway proxy — your agent still calls the model directly

---

## Links

- Docs: https://kalibr.systems/docs
- Dashboard: https://dashboard.kalibr.systems
- Quickstart: https://kalibr.systems/docs/quickstart
- llms.txt: https://kalibr.systems/llms.txt
- setup.txt: https://kalibr.systems/setup.txt
- PyPI: https://pypi.org/project/kalibr/
- GitHub: https://github.com/kalibr-ai/kalibr-sdk-python
