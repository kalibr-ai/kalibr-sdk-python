# Kalibr LangChain Integration

Observability integration for LangChain applications using the Kalibr platform.

## Features

- **Zero-config tracing** of LangChain components (LLMs, chains, tools, agents, retrievers)
- **Token tracking** with automatic extraction from LLM responses
- **Cost calculation** using Kalibr's cost adapters for OpenAI, Anthropic, and more
- **Span hierarchy** for complex chains and agent workflows
- **Error tracking** with stack traces
- **Async support** for async LangChain operations
- **Batched telemetry** for efficient backend communication

## Installation

```bash
# Install with the main kalibr package
pip install kalibr[langchain]

# Or install separately
pip install kalibr-langchain
```

## Quick Start

```python
from kalibr_langchain import KalibrCallbackHandler
from langchain_openai import ChatOpenAI

# Create the callback handler
handler = KalibrCallbackHandler(
    api_key="your-kalibr-api-key",
    tenant_id="my-tenant",
    environment="prod",
)

# Use with any LangChain component
llm = ChatOpenAI(model="gpt-4", callbacks=[handler])
response = llm.invoke("What is the capital of France?")
```

## Configuration

### Environment Variables

The handler can be configured via environment variables:

```bash
export KALIBR_API_KEY="your-api-key"
export KALIBR_ENDPOINT="https://api.kalibr.dev/v1/traces"
export KALIBR_TENANT_ID="my-tenant"
export KALIBR_ENVIRONMENT="prod"
export KALIBR_SERVICE="my-langchain-app"
export KALIBR_WORKFLOW_ID="my-workflow"
```

### Constructor Parameters

```python
handler = KalibrCallbackHandler(
    api_key="...",              # API key for authentication
    endpoint="...",             # Backend endpoint URL
    tenant_id="...",            # Tenant identifier
    environment="prod",         # Environment (prod/staging/dev)
    service="my-app",           # Service name for grouping
    workflow_id="my-workflow",  # Workflow identifier
    capture_input=True,         # Capture input prompts
    capture_output=True,        # Capture outputs
    max_content_length=10000,   # Max length for captured content
    batch_size=100,             # Events per batch
    flush_interval=2.0,         # Flush interval in seconds
    metadata={"key": "value"},  # Additional metadata for all events
)
```

## Usage Examples

### With Chains

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from kalibr_langchain import KalibrCallbackHandler

handler = KalibrCallbackHandler()

# Build a chain
prompt = ChatPromptTemplate.from_template("Tell me a joke about {topic}")
llm = ChatOpenAI(model="gpt-4")
parser = StrOutputParser()

chain = prompt | llm | parser

# Run with callbacks
result = chain.invoke(
    {"topic": "programming"},
    config={"callbacks": [handler]}
)
```

### With Agents

```python
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from kalibr_langchain import KalibrCallbackHandler

handler = KalibrCallbackHandler()

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

llm = ChatOpenAI(model="gpt-4")
agent = create_openai_functions_agent(llm, [search], prompt)
executor = AgentExecutor(agent=agent, tools=[search])

# Run with callbacks
result = executor.invoke(
    {"input": "What is LangChain?"},
    config={"callbacks": [handler]}
)
```

### With Retrievers (RAG)

```python
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from kalibr_langchain import KalibrCallbackHandler

handler = KalibrCallbackHandler()

# Setup retriever
embeddings = OpenAIEmbeddings()
vectorstore = FAISS.from_texts(["LangChain is a framework..."], embeddings)
retriever = vectorstore.as_retriever()

# Run retrieval with callbacks
docs = retriever.invoke(
    "What is LangChain?",
    config={"callbacks": [handler]}
)
```

### Async Operations

```python
import asyncio
from langchain_openai import ChatOpenAI
from kalibr_langchain import AsyncKalibrCallbackHandler

async def main():
    handler = AsyncKalibrCallbackHandler()

    llm = ChatOpenAI(model="gpt-4")

    response = await llm.ainvoke(
        "Hello!",
        config={"callbacks": [handler]}
    )

    # Flush remaining events
    await handler.flush()
    await handler.close()

asyncio.run(main())
```

### Multiple LLMs

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from kalibr_langchain import KalibrCallbackHandler

handler = KalibrCallbackHandler()

# Both LLMs will be traced
openai_llm = ChatOpenAI(model="gpt-4", callbacks=[handler])
anthropic_llm = ChatAnthropic(model="claude-3-sonnet-20240229", callbacks=[handler])

# Traces will show provider and model information
response1 = openai_llm.invoke("Hello from OpenAI!")
response2 = anthropic_llm.invoke("Hello from Anthropic!")
```

## Traced Components

The callback handler traces the following LangChain components:

| Component | Operation | Captured Data |
|-----------|-----------|---------------|
| LLM | `llm_call` | Model, tokens, cost, latency |
| Chat Model | `chat_completion` | Model, messages, tokens, cost |
| Chain | `chain:{name}` | Inputs, outputs, duration |
| Tool | `tool:{name}` | Input, output, duration |
| Agent | `agent_action` | Actions, tool calls |
| Retriever | `retriever:{name}` | Query, documents, count |

## Event Schema

Events sent to Kalibr follow the v1.0 schema:

```json
{
  "schema_version": "1.0",
  "trace_id": "uuid",
  "span_id": "uuid",
  "parent_span_id": "uuid or null",
  "tenant_id": "my-tenant",
  "workflow_id": "my-workflow",
  "provider": "openai",
  "model_id": "gpt-4",
  "operation": "chat_completion",
  "duration_ms": 250,
  "input_tokens": 100,
  "output_tokens": 50,
  "cost_usd": 0.0045,
  "status": "success",
  "timestamp": "2025-01-15T12:00:00.000Z",
  "metadata": {
    "langchain": true,
    "span_type": "chat"
  }
}
```

## Best Practices

1. **Single Handler Instance**: Create one handler and reuse it across your application
2. **Flush on Shutdown**: Call `handler.shutdown()` or `await handler.close()` before exiting
3. **Use Workflow IDs**: Set meaningful workflow IDs to group related traces
4. **Control Capture**: Disable `capture_input`/`capture_output` for sensitive data
5. **Set Service Names**: Use descriptive service names for filtering in dashboards

## License

MIT License - see the main Kalibr SDK license for details.
