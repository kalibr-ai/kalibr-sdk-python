# Kalibr Python SDK

Production-grade observability for LLM applications.

## Installation
```bash
pip install kalibr
```

## Quickstart
```python
from kalibr import trace
import openai

@trace(api_key="your-kalibr-api-key")
def my_agent():
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    return response
```

## Features

- ✅ Zero-code instrumentation for OpenAI, Anthropic, Google AI
- ✅ Automatic parent-child trace relationships
- ✅ Real-time cost tracking
- ✅ Token usage monitoring
- ✅ Performance metrics

## CLI Tools
```bash
# Run your app locally
kalibr serve myapp.py

# Deploy to Fly.io
kalibr deploy myapp.py

# Fetch trace data
kalibr capsule <trace-id>
```

## Examples

See `examples/` directory for complete examples.

## Documentation

Full docs at https://docs.kalibr.systems

## License

MIT
