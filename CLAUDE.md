# Kalibr SDK

LLM observability SDK for Python. Auto-instruments OpenAI, Anthropic, and Google AI calls.

## Quick Commands
```bash
pip install kalibr          # Install
pytest                       # Run tests
ruff check kalibr/          # Lint
black kalibr/               # Format
```

## Structure

- `kalibr/` - Core SDK
- `kalibr/instrumentation/` - Auto-instrumentation for LLM providers
- `kalibr_langchain/` - LangChain integration
- `kalibr_crewai/` - CrewAI integration
- `kalibr_openai_agents/` - OpenAI Agents SDK integration
- `examples/` - Usage examples
- `tests/` - Test suite

## Key Files

- `kalibr/__init__.py` - Public API exports
- `kalibr/client.py` - Main KalibrClient class
- `kalibr/simple_tracer.py` - @trace decorator
- `kalibr/trace_models.py` - Pydantic models for traces
- `kalibr/instrumentation/` - Provider-specific instrumentation

## Environment Variables

- `KALIBR_API_KEY` - API key for authentication
- `KALIBR_API_ENDPOINT` - Override default endpoint
- `KALIBR_COLLECTOR_URL` - Override collector URL
- `KALIBR_AUTO_INSTRUMENT` - Set to "false" to disable auto-instrumentation
