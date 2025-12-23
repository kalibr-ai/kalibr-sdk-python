"""Kalibr LangChain Integration - Observability for LangChain applications.

This package provides a callback handler that integrates LangChain with
Kalibr's observability platform, capturing:
- LLM calls with token usage and costs
- Chain executions with timing
- Tool/Agent invocations
- Retrieval operations
- Error tracking with stack traces

Usage:
    from kalibr_langchain import KalibrCallbackHandler
    from langchain_openai import ChatOpenAI

    # Create callback handler
    handler = KalibrCallbackHandler(
        api_key="your-api-key",
        tenant_id="my-tenant",
    )

    # Use with LangChain
    llm = ChatOpenAI(model="gpt-4", callbacks=[handler])
    response = llm.invoke("Hello, world!")

    # Or attach to all components
    from langchain.globals import set_llm_cache
    chain = prompt | llm | parser
    chain.invoke({"input": "Hello"}, config={"callbacks": [handler]})

Environment Variables:
    KALIBR_API_KEY: API key for authentication
    KALIBR_COLLECTOR_URL: Backend endpoint URL
    KALIBR_TENANT_ID: Tenant identifier
    KALIBR_ENVIRONMENT: Environment (prod/staging/dev)
    KALIBR_SERVICE: Service name
"""

__version__ = "0.1.0"

from .callback import KalibrCallbackHandler
from .async_callback import AsyncKalibrCallbackHandler

__all__ = [
    "KalibrCallbackHandler",
    "AsyncKalibrCallbackHandler",
    "__version__",
]
