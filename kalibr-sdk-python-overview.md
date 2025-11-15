# kalibr-sdk-python

The Python package that customers install with `pip install kalibr`. This SDK automatically tracks LLM API calls across OpenAI, Anthropic, and Google with zero configuration.

---

## Repository Structure

```
kalibr-sdk-python/
├── kalibr/              # Core SDK package (33 Python files)
│   ├── __init__.py      # Public API exports
│   ├── instrumentation/ # Auto-instrumentation for LLM providers
│   ├── cli/             # Command-line tools
│   ├── middleware/      # Framework integration
│   └── ...              # Core modules
├── examples/            # Customer example code (6 files)
├── tests/               # SDK unit tests (2 files)
├── docs/                # Documentation
├── pyproject.toml       # Package configuration for PyPI
├── README.md
└── LICENSE              # MIT License
```

**Total**: 42 Python files

---

## Core Functionality

### Auto-Instrumentation

The SDK uses monkey-patching to automatically intercept LLM API calls when imported.

**How it works** (`instrumentation/openai_instr.py`):
```python
class OpenAIInstrumentation:
    def instrument(self):
        # Save original function
        self._original_create = completions.Completions.create
        
        # Replace with wrapped version
        completions.Completions.create = self._traced_create_wrapper(
            completions.Completions.create
        )
    
    def _traced_create_wrapper(self, original_func):
        def wrapper(*args, **kwargs):
            # Create OpenTelemetry span
            with self.tracer.start_as_current_span("openai.chat.completions.create") as span:
                start_time = time.time()
                
                # Call real OpenAI API
                result = original_func(*args, **kwargs)
                
                # Record metadata
                span.set_attribute("llm.usage.prompt_tokens", result.usage.prompt_tokens)
                span.set_attribute("llm.usage.completion_tokens", result.usage.completion_tokens)
                span.set_attribute("llm.cost_usd", self.calculate_cost(result))
                span.set_attribute("llm.latency_ms", (time.time() - start_time) * 1000)
                
                return result
        return wrapper
```

**What gets captured**:
- Provider (openai, anthropic, google)
- Model name (gpt-4, claude-3-sonnet, gemini-pro)
- Input tokens
- Output tokens
- Cost in USD
- Latency in milliseconds
- Timestamp
- Errors

**Supported providers**:
- OpenAI (`instrumentation/openai_instr.py`)
- Anthropic (`instrumentation/anthropic_instr.py`)
- Google AI (`instrumentation/google_instr.py`)

---

### Cost Calculation

The SDK includes pricing tables for all major models and calculates costs automatically.

**Pricing table** (`instrumentation/openai_instr.py`):
```python
PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},        # per 1K tokens
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}
```

**Cost calculation**:
```python
def calculate_cost(model: str, usage: dict) -> float:
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    
    return round(input_cost + output_cost, 6)
```

---

### Manual Tracing

For custom functions that aren't LLM calls, use the `@trace()` decorator.

**Simple tracer** (`simple_tracer.py`):
```python
@trace(operation="summarize", provider="openai", model="gpt-4o")
def summarize_text(text: str) -> str:
    return openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Summarize: {text}"}]
    )
```

**What the decorator does**:
1. Generates unique trace ID and span ID
2. Records start time
3. Executes the function
4. Records end time and calculates duration
5. Estimates tokens (if not provided)
6. Calculates cost
7. Sends data to Kalibr backend via HTTP POST

**Data sent to backend**:
```python
{
    "trace_id": "abc-123-...",
    "span_id": "def-456-...",
    "parent_id": "parent-span-id",  # For nested calls
    "provider": "openai",
    "model_name": "gpt-4o",
    "operation": "summarize",
    "input_tokens": 1000,
    "output_tokens": 500,
    "duration_ms": 850,
    "cost_usd": 0.0275,
    "status": "success",
    "timestamp": "2025-01-15T10:30:00Z"
}
```

---

### OpenTelemetry Integration

The SDK uses OpenTelemetry as its instrumentation standard.

**Collector setup** (`collector.py`):
```python
def setup_collector(service_name="kalibr"):
    # Create tracer provider
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: service_name})
    )
    
    # Add exporters
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # Send to backend
    provider.add_span_processor(BatchSpanProcessor(FileSpanExporter()))   # Fallback to file
    
    # Set as global provider
    trace.set_tracer_provider(provider)
```

**File exporter fallback**:
If the backend is unreachable, spans are written to `/tmp/kalibr_otel_spans.jsonl` in NDJSON format (one JSON object per line).

---

### Parent-Child Tracing

The SDK automatically links nested function calls.

**Example**:
```python
@trace(operation="research")
def research_topic(topic: str):
    summary = summarize_docs(topic)      # Child trace 1
    analysis = analyze_data(summary)     # Child trace 2
    return analysis

@trace(operation="summarize")
def summarize_docs(topic: str):
    return openai.create(...)            # Grandchild trace

@trace(operation="analyze")
def analyze_data(summary: str):
    return anthropic.create(...)         # Grandchild trace
```

**Trace hierarchy**:
```
research_topic (parent)
├── summarize_docs (child)
│   └── openai.create (grandchild)
└── analyze_data (child)
    └── anthropic.create (grandchild)
```

The dashboard renders this as a tree view showing the complete workflow.

---

## CLI Tools

The SDK includes command-line tools for developers.

**Available commands** (`cli/`):

### `kalibr serve`
Runs applications locally with auto-tracing enabled.
```bash
kalibr serve myapp.py
```

### `kalibr deploy`
Deploys applications to Fly.io or Render.
```bash
kalibr deploy myapp.py --runtime fly
```

### `kalibr capsule`
Fetches trace data from the backend.
```bash
kalibr capsule abc-123-def --output trace.json
```

### `kalibr run`
Executes applications with managed runtime.
```bash
kalibr run myapp.py
```

---

## Example Usage

### Basic Example
```python
from kalibr import Kalibr

app = Kalibr(title="Weather API")

@app.action("get_weather", "Get current weather")
def get_weather(location: str) -> dict:
    return {
        "location": location,
        "temperature": 22,
        "condition": "Sunny"
    }

if __name__ == "__main__":
    app.run()
```

### Auto-Instrumentation Example
```python
import kalibr  # Automatically instruments OpenAI/Anthropic/Google
import openai

# This call is automatically tracked - no decorators needed!
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Multi-Provider Example
```python
from kalibr import trace
import openai
import anthropic

@trace(operation="multi_model_chat")
def chat_with_models(prompt: str):
    # Both calls automatically tracked and linked
    gpt_response = openai.chat.completions.create(model="gpt-4", messages=[...])
    claude_response = anthropic.messages.create(model="claude-3-sonnet", messages=[...])
    
    return {
        "gpt4": gpt_response,
        "claude": claude_response
    }
```

---

## Data Flow

```
Customer imports kalibr
    ↓
Auto-instrumentation patches OpenAI/Anthropic/Google SDKs
    ↓
Customer calls openai.create(...)
    ↓
Instrumentation intercepts the call
    ↓
Records: model, tokens, timestamp
    ↓
Calls real OpenAI API
    ↓
Records: response tokens, cost, latency
    ↓
Creates OpenTelemetry span
    ↓
Sends span to Kalibr backend (HTTP POST)
    ↓
If backend unreachable: writes to local JSONL file
    ↓
Returns result to customer (transparent - customer sees normal response)
```

---

## Key Design Principles

**Zero Configuration**: Just `import kalibr` and LLM calls are automatically tracked.

**Non-Invasive**: If Kalibr fails, customer's code still works. The instrumentation never breaks their application.

**Multi-Provider**: Works with OpenAI, Anthropic, and Google simultaneously.

**OpenTelemetry Standard**: Uses OTel for interoperability with other observability tools.

**Fallback Storage**: If backend is down, data is saved locally and can be uploaded later.

**Parent-Child Linking**: Automatically traces relationships between nested calls.

---

## Configuration

All configuration through environment variables:

```bash
# Backend endpoint
export KALIBR_COLLECTOR_URL="https://api.kalibr.systems/api/ingest"

# API key for authentication
export KALIBR_API_KEY="your-api-key"

# Service name (for OpenTelemetry)
export KALIBR_SERVICE_NAME="my-ai-app"

# Tenant/Organization ID
export KALIBR_TENANT_ID="org-xyz"

# Disable auto-instrumentation (if needed)
export KALIBR_AUTO_INSTRUMENT="false"
```

---

## What Customers Get

When developers use this SDK:

✅ **Automatic cost tracking** - See exactly what each LLM call costs  
✅ **Multi-provider visibility** - OpenAI + Anthropic + Google in one dashboard  
✅ **Token usage monitoring** - Input/output tokens per call  
✅ **Latency metrics** - How fast each call responds  
✅ **Workflow visualization** - See parent-child trace relationships  
✅ **Error tracking** - Automatic error capture with stack traces  
✅ **Zero configuration** - Just `import kalibr` and it works  

---

## Package Distribution

**PyPI package** (`pyproject.toml`):
```toml
[project]
name = "kalibr"
version = "1.1.0"
description = "LLM observability and cost tracking"
dependencies = [
    "opentelemetry-api",
    "opentelemetry-sdk",
    "openai",
    "anthropic",
    "google-generativeai",
    "requests",
    "pydantic"
]

[project.scripts]
kalibr = "kalibr.cli.main:cli"
```

Customers install with:
```bash
pip install kalibr
```

---

## Summary

The **kalibr-sdk-python** repository contains the customer-facing Python package. It automatically instruments OpenAI, Anthropic, and Google AI SDKs to track costs, tokens, and performance. The SDK uses OpenTelemetry standards, requires zero configuration, and provides CLI tools for deployment and debugging.