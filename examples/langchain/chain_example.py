"""Chain usage with Kalibr LangChain integration.

This example shows how to trace LangChain chains with the KalibrCallbackHandler.
You'll see nested spans for each component in the chain.

Prerequisites:
    pip install kalibr langchain-openai
    export OPENAI_API_KEY="your-openai-key"
    export KALIBR_API_KEY="your-kalibr-key"
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from kalibr_langchain import KalibrCallbackHandler


def main():
    # Create the Kalibr callback handler
    handler = KalibrCallbackHandler(
        tenant_id="demo-tenant",
        environment="dev",
        service="langchain-chain-demo",
        workflow_id="joke-generation",  # Group related traces
    )

    # Build a chain using LCEL (LangChain Expression Language)
    prompt = ChatPromptTemplate.from_template(
        "You are a comedian. Tell me a short joke about {topic}. "
        "Keep it family-friendly and under 50 words."
    )
    llm = ChatOpenAI(model="gpt-4o-mini")
    parser = StrOutputParser()

    # Create the chain
    chain = prompt | llm | parser

    # Run the chain with callbacks - all components will be traced
    print("Generating jokes about different topics...")

    topics = ["programming", "coffee", "meetings"]

    for topic in topics:
        print(f"\nTopic: {topic}")
        result = chain.invoke(
            {"topic": topic},
            config={"callbacks": [handler]}
        )
        print(f"Joke: {result}")

    # Flush and shutdown
    handler.flush()
    handler.shutdown()

    print("\nDone! Check your Kalibr dashboard for the chain traces.")
    print("You should see parent-child relationships between chain and LLM spans.")


if __name__ == "__main__":
    main()
