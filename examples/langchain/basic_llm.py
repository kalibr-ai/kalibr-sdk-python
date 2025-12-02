"""Basic LLM usage with Kalibr LangChain integration.

This example shows how to use the KalibrCallbackHandler with a simple
ChatOpenAI LLM call.

Prerequisites:
    pip install kalibr langchain-openai
    export OPENAI_API_KEY="your-openai-key"
    export KALIBR_API_KEY="your-kalibr-key"
"""

import os
from langchain_openai import ChatOpenAI
from kalibr_langchain import KalibrCallbackHandler


def main():
    # Create the Kalibr callback handler
    # It will automatically read configuration from environment variables:
    # - KALIBR_API_KEY
    # - KALIBR_ENDPOINT
    # - KALIBR_TENANT_ID
    # - KALIBR_ENVIRONMENT
    handler = KalibrCallbackHandler(
        tenant_id="demo-tenant",
        environment="dev",
        service="langchain-demo",
    )

    # Create the LLM with the callback handler
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        callbacks=[handler],
    )

    # Make some LLM calls - all will be traced automatically
    print("Making LLM calls...")

    response1 = llm.invoke("What is the capital of France?")
    print(f"Response 1: {response1.content[:100]}...")

    response2 = llm.invoke("What is the population of Paris?")
    print(f"Response 2: {response2.content[:100]}...")

    # Force flush any remaining events
    handler.flush()

    # Clean shutdown
    handler.shutdown()

    print("\nDone! Check your Kalibr dashboard for traces.")


if __name__ == "__main__":
    main()
